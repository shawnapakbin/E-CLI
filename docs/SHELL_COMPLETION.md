# Shell Completion Installation Guide

E-CLI provides shell completion scripts for Bash, Zsh, and Fish shells. These enable tab completion for commands, subcommands, and options.

## Installation Instructions

### Bash

#### Option 1: User-level installation (recommended)
```bash
# Create completions directory if it doesn't exist
mkdir -p ~/.local/share/bash-completion/completions

# Copy completion script
cp scripts/completions/e-cli-completion.bash ~/.local/share/bash-completion/completions/e-cli

# Source in your .bashrc
echo 'source ~/.local/share/bash-completion/completions/e-cli' >> ~/.bashrc

# Reload shell
source ~/.bashrc
```

#### Option 2: System-wide installation (requires sudo)
```bash
# Copy to system completions directory
sudo cp scripts/completions/e-cli-completion.bash /etc/bash_completion.d/e-cli

# Reload shell
source /etc/bash_completion.d/e-cli
```

### Zsh

#### Option 1: User-level installation (recommended)
```bash
# Create completions directory if it doesn't exist
mkdir -p ~/.zsh/completions

# Copy completion script
cp scripts/completions/_e-cli ~/.zsh/completions/

# Add to fpath in your .zshrc (if not already done)
echo 'fpath=(~/.zsh/completions $fpath)' >> ~/.zshrc
echo 'autoload -Uz compinit && compinit' >> ~/.zshrc

# Reload shell
exec zsh
```

#### Option 2: System-wide installation (requires sudo)
```bash
# Copy to system completions directory
sudo cp scripts/completions/_e-cli /usr/local/share/zsh/site-functions/

# Reload completion system
rm -f ~/.zcompdump
exec zsh
```

### Fish

```bash
# Create completions directory if it doesn't exist
mkdir -p ~/.config/fish/completions

# Copy completion script
cp scripts/completions/e-cli.fish ~/.config/fish/completions/

# Fish will automatically load it on next shell start
# Or reload manually:
source ~/.config/fish/completions/e-cli.fish
```

## Verification

After installation, test the completion by typing:

```bash
e-cli <TAB>
```

You should see available commands like `chat`, `doctor`, `models`, etc.

Try completing subcommands:

```bash
e-cli models <TAB>
e-cli config set --<TAB>
```

## Features

The completion scripts provide:

- **Command completion**: Tab-complete main commands and subcommands
- **Option completion**: Complete flag names (--provider, --model, etc.)
- **Value completion**: Complete specific values like provider names, approval modes
- **Context-aware**: Different completions based on which command/subcommand you're in
- **Help text**: Descriptions for commands and options (Zsh and Fish)

## Troubleshooting

### Bash completions not working

1. Check if bash-completion is installed:
   ```bash
   # On Ubuntu/Debian
   sudo apt-get install bash-completion

   # On macOS with Homebrew
   brew install bash-completion
   ```

2. Ensure your .bashrc sources completion:
   ```bash
   # Add to .bashrc if missing
   if [ -f /etc/bash_completion ]; then
       . /etc/bash_completion
   fi
   ```

### Zsh completions not working

1. Make sure compinit is called in .zshrc:
   ```bash
   autoload -Uz compinit && compinit
   ```

2. Clear the completion cache:
   ```bash
   rm -f ~/.zcompdump*
   exec zsh
   ```

3. Check if the completions directory is in fpath:
   ```bash
   echo $fpath
   ```

### Fish completions not working

1. Verify Fish version (3.0+ required):
   ```bash
   fish --version
   ```

2. Check completions directory:
   ```bash
   echo $fish_complete_path
   ```

3. Manually reload completions:
   ```bash
   fish_update_completions
   ```

## Uninstallation

### Bash
```bash
rm ~/.local/share/bash-completion/completions/e-cli
# Or for system-wide:
sudo rm /etc/bash_completion.d/e-cli
```

### Zsh
```bash
rm ~/.zsh/completions/_e-cli
# Or for system-wide:
sudo rm /usr/local/share/zsh/site-functions/_e-cli
```

### Fish
```bash
rm ~/.config/fish/completions/e-cli.fish
```

## Development

To modify the completion scripts:

1. Edit the appropriate script in `scripts/completions/`
2. Test your changes by sourcing the script directly
3. Report issues or contribute improvements via GitHub

## Supported Shells

- Bash 4.0+
- Zsh 5.0+
- Fish 3.0+

Other shells are not currently supported. If you'd like completion for another shell, please open an issue or submit a pull request.
