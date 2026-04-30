#!/usr/bin/env bash
# Bash completion script for e-cli
# Install: source this file or copy to /etc/bash_completion.d/

_e_cli_completion() {
    local cur prev opts base
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Main commands
    local commands="chat doctor models safe-mode approval sessions tools config skills wiki workflow"

    # Subcommands for each main command
    local models_cmds="list test choose"
    local safe_mode_cmds="on off status"
    local approval_cmds="set show"
    local sessions_cmds="list show delete compact audit stats"
    local tools_cmds="list run"
    local config_cmds="show set reset"
    local skills_cmds="list info enable disable reload install search stats"
    local wiki_cmds="init create list search show delete index stats backlinks"
    local workflow_cmds="list show run create delete"

    # Options for various commands
    local common_opts="--help"
    local doctor_opts="--fix --all --interactive --batch --api --tools --memory --config"
    local config_set_opts="--provider --model --endpoint --temperature --top-p --max-output-tokens --safe-mode --no-safe-mode --streaming-enabled --no-streaming-enabled"
    local models_list_opts="--choose --provider"
    local sessions_opts="--last --id --limit"
    local tools_run_opts="--tool --command --url --path"
    local skills_opts="--category --tag --disabled"
    local wiki_opts="--category --tag --title --content"
    local workflow_opts="--tag --param --dry-run --global --force --verbose"

    # Provider options
    local providers="ollama lmstudio vllm openai anthropic google"

    # Approval modes
    local approval_modes="always ask never"

    # Completion logic
    if [[ ${COMP_CWORD} -eq 1 ]]; then
        # Complete main commands
        COMPREPLY=( $(compgen -W "${commands} ${common_opts}" -- ${cur}) )
        return 0
    fi

    case "${COMP_WORDS[1]}" in
        doctor)
            COMPREPLY=( $(compgen -W "${doctor_opts} ${common_opts}" -- ${cur}) )
            return 0
            ;;
        models)
            if [[ ${COMP_CWORD} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${models_cmds} ${common_opts}" -- ${cur}) )
            else
                case "${COMP_WORDS[2]}" in
                    list)
                        COMPREPLY=( $(compgen -W "${models_list_opts} ${common_opts}" -- ${cur}) )
                        ;;
                esac
            fi
            return 0
            ;;
        safe-mode)
            if [[ ${COMP_CWORD} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${safe_mode_cmds} ${common_opts}" -- ${cur}) )
            fi
            return 0
            ;;
        approval)
            if [[ ${COMP_CWORD} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${approval_cmds} ${common_opts}" -- ${cur}) )
            else
                case "${COMP_WORDS[2]}" in
                    set)
                        if [[ ${prev} == "--mode" ]] || [[ ${prev} == "-m" ]]; then
                            COMPREPLY=( $(compgen -W "${approval_modes}" -- ${cur}) )
                        else
                            COMPREPLY=( $(compgen -W "--mode -m ${common_opts}" -- ${cur}) )
                        fi
                        ;;
                esac
            fi
            return 0
            ;;
        sessions)
            if [[ ${COMP_CWORD} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${sessions_cmds} ${common_opts}" -- ${cur}) )
            else
                COMPREPLY=( $(compgen -W "${sessions_opts} ${common_opts}" -- ${cur}) )
            fi
            return 0
            ;;
        tools)
            if [[ ${COMP_CWORD} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${tools_cmds} ${common_opts}" -- ${cur}) )
            else
                COMPREPLY=( $(compgen -W "${tools_run_opts} ${common_opts}" -- ${cur}) )
            fi
            return 0
            ;;
        config)
            if [[ ${COMP_CWORD} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${config_cmds} ${common_opts}" -- ${cur}) )
            else
                case "${COMP_WORDS[2]}" in
                    set)
                        if [[ ${prev} == "--provider" ]]; then
                            COMPREPLY=( $(compgen -W "${providers}" -- ${cur}) )
                        else
                            COMPREPLY=( $(compgen -W "${config_set_opts} ${common_opts}" -- ${cur}) )
                        fi
                        ;;
                esac
            fi
            return 0
            ;;
        skills)
            if [[ ${COMP_CWORD} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${skills_cmds} ${common_opts}" -- ${cur}) )
            else
                COMPREPLY=( $(compgen -W "${skills_opts} ${common_opts}" -- ${cur}) )
            fi
            return 0
            ;;
        wiki)
            if [[ ${COMP_CWORD} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${wiki_cmds} ${common_opts}" -- ${cur}) )
            else
                COMPREPLY=( $(compgen -W "${wiki_opts} ${common_opts}" -- ${cur}) )
            fi
            return 0
            ;;
        workflow)
            if [[ ${COMP_CWORD} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${workflow_cmds} ${common_opts}" -- ${cur}) )
            else
                COMPREPLY=( $(compgen -W "${workflow_opts} ${common_opts}" -- ${cur}) )
            fi
            return 0
            ;;
        chat)
            COMPREPLY=( $(compgen -W "${common_opts}" -- ${cur}) )
            return 0
            ;;
    esac
}

# Register completion function
complete -F _e_cli_completion e-cli
