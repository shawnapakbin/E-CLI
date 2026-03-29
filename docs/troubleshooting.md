# Troubleshooting E-CLI

## Common Issues

### E-CLI not found after install
- Open a new terminal after install
- Ensure Python user scripts directory is in your PATH

### Model not responding
- Check that the model server is running and reachable
- Use `e-cli models list` and `e-cli models test`

### Tool or skill not working
- Use `e-cli tools list` to inspect available tools
- Use `e-cli skills-list` to inspect available skills

### Permission or approval errors
- Check safe mode and approval mode settings
- Use `e-cli safe-mode status` and `e-cli approval status`

### Memory or session issues
- Use `e-cli doctor` to check memory DB
- Use `e-cli sessions compact` to reduce memory usage
