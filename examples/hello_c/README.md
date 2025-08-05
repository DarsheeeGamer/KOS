# hello_c

A KOS application written in C.

## Description

This is a template application for KOS (Kaede Operating System). It demonstrates the basic structure and conventions for developing KOS applications.

## Building

### Prerequisites

- KOS SDK installed
- C development tools

### Build Instructions

```bash
# Build the application
kos-build

# Or manually:
make
```

## Running

```bash
# Run the application
./hello_c

# Or through KOS runtime:
kos-run hello_c
```

## Project Structure

```
hello_c/
├── src/            # Source files
├── include/        # Header files (C/C++)
├── tests/          # Test files
├── docs/           # Documentation
├── kos-project.json  # Project configuration
└── README.md       # This file
```

## Development

### Adding New Features

1. Create new source files in `src/`
2. Add headers to `include/` (for C/C++)
3. Update `kos-project.json` with new files
4. Rebuild the project

### Testing

```bash
# Run tests
kos-test
```

## License

This is a template project. Add your license here.

## Contributing

Contributions are welcome! Please read the contributing guidelines first.
