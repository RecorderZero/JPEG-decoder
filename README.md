# Dependencies
- uv
- make

## make
### MACOS installation
Install make using Homebrew:
```bash
brew install make
```

### Ubuntu installation
Install make using apt:
```bash
apt-get install make
```

## uv installation
```bash
make install-uv
```

# Structure of the project
```
jpeg-decoder/
├── main.py
├── Makefile
├── pyproject.toml
├── README.md
└── src/
    ├── jpeg_decoder/
    │   ├── image.py
    │   ├── ppm.py
    │   ├── decoder.py
    │   ├── marker.py
    │   └── reader.py
```

# Usage
```bash
uv run main.py --help
```

# Unit Tests

Run all tests:
```bash
uv run pytest tests/ -v
```

## Test Coverage

Tests are located in `tests/test_marker.py` and cover the JPEG marker parsing functions:

| Test Class | Description |
|------------|-------------|
| `TestParseApp0` | APP0/JFIF segment parsing (identifier, version, density, thumbnails) |
| `TestParseDqt` | Quantization table parsing (8-bit/16-bit precision, multiple tables) |
| `TestParseDht` | Huffman table parsing (DC/AC tables, code generation) |
| `TestParseSof0` | Start of Frame parsing (dimensions, components, sampling factors) |
| `TestParseSos` | Start of Scan parsing (component table mappings) |
| `TestBrokenJpegFile` | Error handling for malformed/truncated JPEG files |
| `TestHelperFunctions` | `read_u8` and `read_u16` helper functions |