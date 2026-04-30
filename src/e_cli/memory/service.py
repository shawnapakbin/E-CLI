"""Higher-level memory service that converts storage entries to model messages."""

from __future__ import annotations

from dataclasses import dataclass

from e_cli.memory.store import AuditEvent, ConversationSummary, MemoryEntry, MemoryStore, SessionSummary
from e_cli.models.base import ModelMessage


@dataclass(frozen=True)
class SessionCompactionResult:
    """Describes the outcome of explicit session compaction."""

    sessionId: str
    originalEntryCount: int
    retainedEntryCount: int
    compactedEntryCount: int
    deletedEntryCount: int
    coveredUntilId: int
    estimatedTokensCompacted: int
    dryRun: bool


class MemoryService:
    """Coordinates memory persistence and retrieval for agent conversations."""

    def __init__(self, memoryStore: MemoryStore) -> None:
        """Stores memory backend dependency for read/write operations."""

        self.memoryStore = memoryStore

    def appendMessage(self, sessionId: str, role: str, content: str) -> None:
        """Persists one message to long-term session memory."""

        try:
            self.memoryStore.append(sessionId=sessionId, role=role, content=content)
        except Exception as exc:
            raise RuntimeError(f"Failed to append message to memory service: {exc}") from exc

    @staticmethod
    def _estimateTokenCount(text: str) -> int:
        """Approximate token count cheaply enough for local context budgeting."""

        normalized = text.strip()
        if not normalized:
            return 1
        return max(1, len(normalized) // 4)

    @staticmethod
    def _buildSummary(entries: list[MemoryEntry]) -> str:
        """Build a compact deterministic summary for older omitted session entries."""

        summaryLines: list[str] = []
        for entry in entries[-12:]:
            preview = entry.content.replace("\n", " ").strip()
            if len(preview) > 180:
                preview = preview[:180] + "..."
            summaryLines.append(f"- {entry.role}: {preview}")
        header = "Prior conversation summary:"
        return "\n".join([header, *summaryLines]) if summaryLines else header

    @staticmethod
    def _mergeSummaryContent(existingSummary: str | None, compactedEntries: list[MemoryEntry]) -> str:
        """Merge an existing persisted summary with freshly compacted entries."""

        sections: list[str] = []
        if existingSummary:
            sections.append(existingSummary.strip())
        if compactedEntries:
            sections.append(MemoryService._buildSummary(compactedEntries))
        return "\n\n".join(section for section in sections if section).strip()

    def getConversationSummary(self, sessionId: str) -> ConversationSummary | None:
        """Expose the persisted session summary for CLI inspection flows."""

        try:
            return self.memoryStore.getConversationSummary(sessionId=sessionId)
        except Exception as exc:
            raise RuntimeError(f"Failed to load conversation summary: {exc}") from exc

    def loadConversation(
        self,
        sessionId: str,
        maxTokens: int = 3200,
        summaryTokens: int = 800,
    ) -> list[ModelMessage]:
        """Load session memory under a token budget, with summary fallback for older turns."""

        try:
            entries = self.memoryStore.listAllBySession(sessionId=sessionId)
            persistedSummary = self.memoryStore.getConversationSummary(sessionId=sessionId)
            if not entries:
                if persistedSummary is None:
                    return []
                return [ModelMessage(role="system", content=persistedSummary.content)]

            summaryMessages: list[ModelMessage] = []
            if persistedSummary is not None and persistedSummary.coveredUntilId < entries[0].id:
                summaryMessages.append(ModelMessage(role="system", content=persistedSummary.content))

            if not entries:
                return []

            recentBudget = max(400, maxTokens - summaryTokens)
            selectedEntries: list[MemoryEntry] = []
            usedTokens = 0
            for entry in reversed(entries):
                entryTokens = self._estimateTokenCount(entry.content) + 8
                if selectedEntries and usedTokens + entryTokens > recentBudget:
                    break
                selectedEntries.append(entry)
                usedTokens += entryTokens
            if not selectedEntries:
                selectedEntries.append(entries[-1])

            selectedEntries.reverse()
            omittedCount = len(entries) - len(selectedEntries)
            messages = [ModelMessage(role=entry.role, content=entry.content) for entry in selectedEntries]
            if omittedCount <= 0:
                return [*summaryMessages, *messages]

            omittedEntries = entries[:omittedCount]
            coveredUntilId = omittedEntries[-1].id
            if persistedSummary is None or persistedSummary.coveredUntilId != coveredUntilId:
                summaryContent = self._mergeSummaryContent(
                    existingSummary=(persistedSummary.content if persistedSummary is not None else None),
                    compactedEntries=omittedEntries,
                )
                self.memoryStore.upsertConversationSummary(
                    sessionId=sessionId,
                    content=summaryContent,
                    coveredUntilId=coveredUntilId,
                )
            else:
                summaryContent = persistedSummary.content

            return [ModelMessage(role="system", content=summaryContent), *messages]
        except Exception as exc:
            raise RuntimeError(f"Failed to load conversation memory: {exc}") from exc

    def compactSession(
        self,
        sessionId: str,
        keepRecent: int = 8,
        targetTokens: int = 2400,
        dryRun: bool = False,
        replaceExistingSummary: bool = False,
    ) -> SessionCompactionResult:
        """Compact older session history into a persisted summary and prune raw entries."""

        try:
            entries = self.memoryStore.listAllBySession(sessionId=sessionId)
            if not entries:
                raise RuntimeError(f"No messages found for session: {sessionId}")

            normalizedKeepRecent = max(1, keepRecent)
            normalizedTargetTokens = max(200, targetTokens)

            retainedEntries: list[MemoryEntry] = []
            usedTokens = 0
            for entry in reversed(entries):
                entryTokens = self._estimateTokenCount(entry.content) + 8
                if len(retainedEntries) < normalizedKeepRecent:
                    retainedEntries.append(entry)
                    usedTokens += entryTokens
                    continue
                if usedTokens + entryTokens > normalizedTargetTokens:
                    break
                retainedEntries.append(entry)
                usedTokens += entryTokens

            retainedEntries.reverse()
            compactedEntries = entries[: len(entries) - len(retainedEntries)]
            if not compactedEntries:
                return SessionCompactionResult(
                    sessionId=sessionId,
                    originalEntryCount=len(entries),
                    retainedEntryCount=len(retainedEntries),
                    compactedEntryCount=0,
                    deletedEntryCount=0,
                    coveredUntilId=0,
                    estimatedTokensCompacted=0,
                    dryRun=dryRun,
                )

            existingSummary = None if replaceExistingSummary else self.memoryStore.getConversationSummary(sessionId=sessionId)
            summaryContent = self._mergeSummaryContent(
                existingSummary=(existingSummary.content if existingSummary is not None else None),
                compactedEntries=compactedEntries,
            )
            coveredUntilId = compactedEntries[-1].id
            estimatedTokensCompacted = sum(self._estimateTokenCount(entry.content) + 8 for entry in compactedEntries)

            deletedEntryCount = 0
            if not dryRun:
                self.memoryStore.upsertConversationSummary(
                    sessionId=sessionId,
                    content=summaryContent,
                    coveredUntilId=coveredUntilId,
                )
                deletedEntryCount = self.memoryStore.deleteEntriesThrough(sessionId=sessionId, throughId=coveredUntilId)

            return SessionCompactionResult(
                sessionId=sessionId,
                originalEntryCount=len(entries),
                retainedEntryCount=len(retainedEntries),
                compactedEntryCount=len(compactedEntries),
                deletedEntryCount=deletedEntryCount,
                coveredUntilId=coveredUntilId,
                estimatedTokensCompacted=estimatedTokensCompacted,
                dryRun=dryRun,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to compact session memory: {exc}") from exc

    def loadEntries(self, sessionId: str, limit: int = 40) -> list[MemoryEntry]:
        """Loads raw session entries for CLI inspection commands."""

        try:
            return self.memoryStore.listBySession(sessionId=sessionId, limit=limit)
        except Exception as exc:
            raise RuntimeError(f"Failed to load session entries: {exc}") from exc

    def listSessions(self, limit: int = 20) -> list[SessionSummary]:
        """Loads recent session summaries for session listing commands."""

        try:
            return self.memoryStore.listSessions(limit=limit)
        except Exception as exc:
            raise RuntimeError(f"Failed to list session summaries: {exc}") from exc

    def appendAuditEvent(
        self,
        sessionId: str,
        action: str,
        tool: str,
        approved: bool,
        status: str,
        reason: str,
        details: str,
    ) -> None:
        """Persist one audit event for approval or tool execution activity."""

        try:
            self.memoryStore.appendAuditEvent(
                sessionId=sessionId,
                action=action,
                tool=tool,
                approved=approved,
                status=status,
                reason=reason,
                details=details,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to append audit event: {exc}") from exc

    def listAuditEvents(self, sessionId: str, limit: int = 20) -> list[AuditEvent]:
        """Load persisted audit events for one session."""

        try:
            return self.memoryStore.listAuditEvents(sessionId=sessionId, limit=limit)
        except Exception as exc:
            raise RuntimeError(f"Failed to list audit events: {exc}") from exc
