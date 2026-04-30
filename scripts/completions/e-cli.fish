# Fish completion script for e-cli
# Install: Copy to ~/.config/fish/completions/e-cli.fish

# Main commands
complete -c e-cli -f -n '__fish_use_subcommand' -a 'chat' -d 'Start interactive chat session'
complete -c e-cli -f -n '__fish_use_subcommand' -a 'doctor' -d 'Run diagnostics and health checks'
complete -c e-cli -f -n '__fish_use_subcommand' -a 'models' -d 'Model discovery and selection'
complete -c e-cli -f -n '__fish_use_subcommand' -a 'safe-mode' -d 'Safe mode controls'
complete -c e-cli -f -n '__fish_use_subcommand' -a 'approval' -d 'Approval mode controls'
complete -c e-cli -f -n '__fish_use_subcommand' -a 'sessions' -d 'Session memory commands'
complete -c e-cli -f -n '__fish_use_subcommand' -a 'tools' -d 'Tool inspection and execution'
complete -c e-cli -f -n '__fish_use_subcommand' -a 'config' -d 'Configuration management'
complete -c e-cli -f -n '__fish_use_subcommand' -a 'skills' -d 'Skills and plugins management'
complete -c e-cli -f -n '__fish_use_subcommand' -a 'wiki' -d 'Knowledge wiki management'
complete -c e-cli -f -n '__fish_use_subcommand' -a 'workflow' -d 'Workflow and macro management'

# Doctor command options
complete -c e-cli -f -n '__fish_seen_subcommand_from doctor' -l fix -d 'Run automatic fixes'
complete -c e-cli -f -n '__fish_seen_subcommand_from doctor' -l all -d 'Run all diagnostics'
complete -c e-cli -f -n '__fish_seen_subcommand_from doctor' -l interactive -d 'Force interactive mode'
complete -c e-cli -f -n '__fish_seen_subcommand_from doctor' -l batch -d 'Force batch mode'
complete -c e-cli -f -n '__fish_seen_subcommand_from doctor' -l api -d 'Check API connectivity'
complete -c e-cli -f -n '__fish_seen_subcommand_from doctor' -l tools -d 'Check tool availability'
complete -c e-cli -f -n '__fish_seen_subcommand_from doctor' -l memory -d 'Check memory system'
complete -c e-cli -f -n '__fish_seen_subcommand_from doctor' -l config -d 'Check configuration'

# Models subcommands
complete -c e-cli -f -n '__fish_seen_subcommand_from models; and not __fish_seen_subcommand_from list test choose' -a 'list' -d 'List available models'
complete -c e-cli -f -n '__fish_seen_subcommand_from models; and not __fish_seen_subcommand_from list test choose' -a 'test' -d 'Test model connection'
complete -c e-cli -f -n '__fish_seen_subcommand_from models; and not __fish_seen_subcommand_from list test choose' -a 'choose' -d 'Choose a model interactively'

# Models list options
complete -c e-cli -f -n '__fish_seen_subcommand_from models; and __fish_seen_subcommand_from list' -l choose -d 'Choose a model after listing'
complete -c e-cli -f -n '__fish_seen_subcommand_from models; and __fish_seen_subcommand_from list' -l provider -d 'Filter by provider' -a 'ollama lmstudio vllm openai anthropic google'

# Safe-mode subcommands
complete -c e-cli -f -n '__fish_seen_subcommand_from safe-mode; and not __fish_seen_subcommand_from on off status' -a 'on' -d 'Enable safe mode'
complete -c e-cli -f -n '__fish_seen_subcommand_from safe-mode; and not __fish_seen_subcommand_from on off status' -a 'off' -d 'Disable safe mode'
complete -c e-cli -f -n '__fish_seen_subcommand_from safe-mode; and not __fish_seen_subcommand_from on off status' -a 'status' -d 'Show safe mode status'

# Approval subcommands
complete -c e-cli -f -n '__fish_seen_subcommand_from approval; and not __fish_seen_subcommand_from set show' -a 'set' -d 'Set approval mode'
complete -c e-cli -f -n '__fish_seen_subcommand_from approval; and not __fish_seen_subcommand_from set show' -a 'show' -d 'Show current approval mode'

# Approval set options
complete -c e-cli -f -n '__fish_seen_subcommand_from approval; and __fish_seen_subcommand_from set' -l mode -s m -d 'Approval mode' -a 'always ask never'

# Sessions subcommands
complete -c e-cli -f -n '__fish_seen_subcommand_from sessions; and not __fish_seen_subcommand_from list show delete compact audit stats' -a 'list' -d 'List all sessions'
complete -c e-cli -f -n '__fish_seen_subcommand_from sessions; and not __fish_seen_subcommand_from list show delete compact audit stats' -a 'show' -d 'Show session details'
complete -c e-cli -f -n '__fish_seen_subcommand_from sessions; and not __fish_seen_subcommand_from list show delete compact audit stats' -a 'delete' -d 'Delete a session'
complete -c e-cli -f -n '__fish_seen_subcommand_from sessions; and not __fish_seen_subcommand_from list show delete compact audit stats' -a 'compact' -d 'Compact session memory'
complete -c e-cli -f -n '__fish_seen_subcommand_from sessions; and not __fish_seen_subcommand_from list show delete compact audit stats' -a 'audit' -d 'View session audit log'
complete -c e-cli -f -n '__fish_seen_subcommand_from sessions; and not __fish_seen_subcommand_from list show delete compact audit stats' -a 'stats' -d 'Show session statistics'

# Sessions options
complete -c e-cli -f -n '__fish_seen_subcommand_from sessions' -l last -d 'Use last session'
complete -c e-cli -f -n '__fish_seen_subcommand_from sessions' -l id -d 'Session ID'
complete -c e-cli -f -n '__fish_seen_subcommand_from sessions' -l limit -d 'Limit results'

# Tools subcommands
complete -c e-cli -f -n '__fish_seen_subcommand_from tools; and not __fish_seen_subcommand_from list run' -a 'list' -d 'List available tools'
complete -c e-cli -f -n '__fish_seen_subcommand_from tools; and not __fish_seen_subcommand_from list run' -a 'run' -d 'Run a tool'

# Tools run options
complete -c e-cli -f -n '__fish_seen_subcommand_from tools; and __fish_seen_subcommand_from run' -l tool -d 'Tool name'
complete -c e-cli -f -n '__fish_seen_subcommand_from tools; and __fish_seen_subcommand_from run' -l command -d 'Shell command'
complete -c e-cli -f -n '__fish_seen_subcommand_from tools; and __fish_seen_subcommand_from run' -l url -d 'URL for HTTP tools'
complete -c e-cli -r -n '__fish_seen_subcommand_from tools; and __fish_seen_subcommand_from run' -l path -d 'File path'

# Config subcommands
complete -c e-cli -f -n '__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from show set reset' -a 'show' -d 'Show current configuration'
complete -c e-cli -f -n '__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from show set reset' -a 'set' -d 'Set configuration values'
complete -c e-cli -f -n '__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from show set reset' -a 'reset' -d 'Reset configuration to defaults'

# Config set options
complete -c e-cli -f -n '__fish_seen_subcommand_from config; and __fish_seen_subcommand_from set' -l provider -d 'LLM provider' -a 'ollama lmstudio vllm openai anthropic google'
complete -c e-cli -f -n '__fish_seen_subcommand_from config; and __fish_seen_subcommand_from set' -l model -d 'Model name'
complete -c e-cli -f -n '__fish_seen_subcommand_from config; and __fish_seen_subcommand_from set' -l endpoint -d 'API endpoint'
complete -c e-cli -f -n '__fish_seen_subcommand_from config; and __fish_seen_subcommand_from set' -l temperature -d 'Temperature'
complete -c e-cli -f -n '__fish_seen_subcommand_from config; and __fish_seen_subcommand_from set' -l top-p -d 'Top-p value'
complete -c e-cli -f -n '__fish_seen_subcommand_from config; and __fish_seen_subcommand_from set' -l max-output-tokens -d 'Max output tokens'
complete -c e-cli -f -n '__fish_seen_subcommand_from config; and __fish_seen_subcommand_from set' -l safe-mode -d 'Enable safe mode'
complete -c e-cli -f -n '__fish_seen_subcommand_from config; and __fish_seen_subcommand_from set' -l no-safe-mode -d 'Disable safe mode'
complete -c e-cli -f -n '__fish_seen_subcommand_from config; and __fish_seen_subcommand_from set' -l streaming-enabled -d 'Enable streaming'
complete -c e-cli -f -n '__fish_seen_subcommand_from config; and __fish_seen_subcommand_from set' -l no-streaming-enabled -d 'Disable streaming'

# Skills subcommands
complete -c e-cli -f -n '__fish_seen_subcommand_from skills; and not __fish_seen_subcommand_from list info enable disable reload install search stats' -a 'list' -d 'List all skills'
complete -c e-cli -f -n '__fish_seen_subcommand_from skills; and not __fish_seen_subcommand_from list info enable disable reload install search stats' -a 'info' -d 'Show skill information'
complete -c e-cli -f -n '__fish_seen_subcommand_from skills; and not __fish_seen_subcommand_from list info enable disable reload install search stats' -a 'enable' -d 'Enable a skill'
complete -c e-cli -f -n '__fish_seen_subcommand_from skills; and not __fish_seen_subcommand_from list info enable disable reload install search stats' -a 'disable' -d 'Disable a skill'
complete -c e-cli -f -n '__fish_seen_subcommand_from skills; and not __fish_seen_subcommand_from list info enable disable reload install search stats' -a 'reload' -d 'Reload a skill'
complete -c e-cli -f -n '__fish_seen_subcommand_from skills; and not __fish_seen_subcommand_from list info enable disable reload install search stats' -a 'install' -d 'Install a skill'
complete -c e-cli -f -n '__fish_seen_subcommand_from skills; and not __fish_seen_subcommand_from list info enable disable reload install search stats' -a 'search' -d 'Search skills'
complete -c e-cli -f -n '__fish_seen_subcommand_from skills; and not __fish_seen_subcommand_from list info enable disable reload install search stats' -a 'stats' -d 'Show skill statistics'

# Skills options
complete -c e-cli -f -n '__fish_seen_subcommand_from skills' -l category -d 'Filter by category'
complete -c e-cli -f -n '__fish_seen_subcommand_from skills' -l tag -d 'Filter by tag'
complete -c e-cli -f -n '__fish_seen_subcommand_from skills' -l disabled -d 'Show disabled skills'

# Wiki subcommands
complete -c e-cli -f -n '__fish_seen_subcommand_from wiki; and not __fish_seen_subcommand_from init create list search show delete index stats backlinks' -a 'init' -d 'Initialize wiki'
complete -c e-cli -f -n '__fish_seen_subcommand_from wiki; and not __fish_seen_subcommand_from init create list search show delete index stats backlinks' -a 'create' -d 'Create a wiki page'
complete -c e-cli -f -n '__fish_seen_subcommand_from wiki; and not __fish_seen_subcommand_from init create list search show delete index stats backlinks' -a 'list' -d 'List all wiki pages'
complete -c e-cli -f -n '__fish_seen_subcommand_from wiki; and not __fish_seen_subcommand_from init create list search show delete index stats backlinks' -a 'search' -d 'Search wiki pages'
complete -c e-cli -f -n '__fish_seen_subcommand_from wiki; and not __fish_seen_subcommand_from init create list search show delete index stats backlinks' -a 'show' -d 'Show page information'
complete -c e-cli -f -n '__fish_seen_subcommand_from wiki; and not __fish_seen_subcommand_from init create list search show delete index stats backlinks' -a 'delete' -d 'Delete a wiki page'
complete -c e-cli -f -n '__fish_seen_subcommand_from wiki; and not __fish_seen_subcommand_from init create list search show delete index stats backlinks' -a 'index' -d 'Rebuild wiki index'
complete -c e-cli -f -n '__fish_seen_subcommand_from wiki; and not __fish_seen_subcommand_from init create list search show delete index stats backlinks' -a 'stats' -d 'Show wiki statistics'
complete -c e-cli -f -n '__fish_seen_subcommand_from wiki; and not __fish_seen_subcommand_from init create list search show delete index stats backlinks' -a 'backlinks' -d 'Show page backlinks'

# Wiki options
complete -c e-cli -f -n '__fish_seen_subcommand_from wiki' -l category -d 'Wiki category'
complete -c e-cli -f -n '__fish_seen_subcommand_from wiki' -l tag -d 'Wiki tag'
complete -c e-cli -f -n '__fish_seen_subcommand_from wiki' -l title -d 'Page title'
complete -c e-cli -f -n '__fish_seen_subcommand_from wiki' -l content -d 'Page content'

# Workflow subcommands
complete -c e-cli -f -n '__fish_seen_subcommand_from workflow; and not __fish_seen_subcommand_from list show run create delete' -a 'list' -d 'List all workflows'
complete -c e-cli -f -n '__fish_seen_subcommand_from workflow; and not __fish_seen_subcommand_from list show run create delete' -a 'show' -d 'Show workflow details'
complete -c e-cli -f -n '__fish_seen_subcommand_from workflow; and not __fish_seen_subcommand_from list show run create delete' -a 'run' -d 'Execute a workflow'
complete -c e-cli -f -n '__fish_seen_subcommand_from workflow; and not __fish_seen_subcommand_from list show run create delete' -a 'create' -d 'Create a new workflow'
complete -c e-cli -f -n '__fish_seen_subcommand_from workflow; and not __fish_seen_subcommand_from list show run create delete' -a 'delete' -d 'Delete a workflow'

# Workflow options
complete -c e-cli -f -n '__fish_seen_subcommand_from workflow' -l tag -s t -d 'Filter by tag'
complete -c e-cli -f -n '__fish_seen_subcommand_from workflow' -l param -s p -d 'Workflow parameter'
complete -c e-cli -f -n '__fish_seen_subcommand_from workflow' -l dry-run -d 'Show execution plan'
complete -c e-cli -f -n '__fish_seen_subcommand_from workflow' -l global -s g -d 'Use global workflows'
complete -c e-cli -f -n '__fish_seen_subcommand_from workflow' -l force -s f -d 'Skip confirmation'
complete -c e-cli -f -n '__fish_seen_subcommand_from workflow' -l verbose -s v -d 'Show detailed output'

# Global help option
complete -c e-cli -f -l help -d 'Show help message'
