"""Unit tests for JPEG marker parsing functions."""
import io
import pytest
import tempfile
import os

from jpeg_decoder.marker import (
    parse_app0,
    parse_dqt,
    parse_dht,
    parse_sof0,
    parse_sos,
    marker_detector,
    read_u8,
    read_u16,
)
from jpeg_decoder.primitives import JPEGMetadata


class TestParseApp0:
    """Tests for parse_app0 function."""

    def test_parse_jfif_header(self):
        """Test parsing a standard JFIF APP0 segment."""
        # APP0 data: JFIF identifier + version + units + density + thumbnail
        app0_data = (
            b"JFIF\x00"  # Identifier (5 bytes)
            b"\x01\x02"  # Version 1.2
            b"\x01"      # Units: dots per inch
            b"\x00\x48"  # X density: 72
            b"\x00\x60"  # Y density: 96
            b"\x00"      # X thumbnail: 0
            b"\x00"      # Y thumbnail: 0
        )
        f = io.BytesIO(app0_data)
        metadata = JPEGMetadata()
        
        parse_app0(f, len(app0_data) + 2, metadata)
        
        assert metadata.app_info.identifier == b"JFIF\x00"
        assert metadata.app_info.version_major_id == 1
        assert metadata.app_info.version_minor_id == 2
        assert metadata.app_info.units == 1
        assert metadata.app_info.x_density == 72
        assert metadata.app_info.y_density == 96
        assert metadata.app_info.x_thumbnail == 0
        assert metadata.app_info.y_thumbnail == 0

    def test_parse_app0_with_thumbnail(self):
        """Test parsing APP0 with thumbnail data."""
        # Small 2x2 thumbnail (12 bytes of RGB data)
        thumbnail_data = b"\xFF" * 12  # 2*2*3 = 12 bytes
        app0_data = (
            b"JFIF\x00"  # Identifier
            b"\x01\x01"  # Version 1.1
            b"\x00"      # Units: no units
            b"\x00\x01"  # X density: 1
            b"\x00\x01"  # Y density: 1
            b"\x02"      # X thumbnail: 2
            b"\x02"      # Y thumbnail: 2
        ) + thumbnail_data
        f = io.BytesIO(app0_data)
        metadata = JPEGMetadata()
        
        parse_app0(f, len(app0_data) + 2, metadata)
        
        assert metadata.app_info.x_thumbnail == 2
        assert metadata.app_info.y_thumbnail == 2
        # File position should be after thumbnail data
        assert f.tell() == len(app0_data)

    def test_parse_app0_dots_per_cm(self):
        """Test parsing APP0 with dots per cm units."""
        app0_data = (
            b"JFIF\x00"
            b"\x01\x00"  # Version 1.0
            b"\x02"      # Units: dots per cm
            b"\x00\x1C"  # X density: 28 (approx 72 dpi)
            b"\x00\x1C"  # Y density: 28
            b"\x00\x00"  # No thumbnail
        )
        f = io.BytesIO(app0_data)
        metadata = JPEGMetadata()
        
        parse_app0(f, len(app0_data) + 2, metadata)
        
        assert metadata.app_info.units == 2
        assert metadata.app_info.x_density == 28
        assert metadata.app_info.y_density == 28


class TestParseDqt:
    """Tests for parse_dqt function."""

    def test_parse_single_8bit_table(self):
        """Test parsing a single 8-bit quantization table."""
        # Table info: precision=0 (8-bit), table_id=0
        table_info = b"\x00"
        # 64 quantization values (simple sequence for testing)
        quant_values = bytes(range(64))
        dqt_data = table_info + quant_values
        
        f = io.BytesIO(dqt_data)
        metadata = JPEGMetadata()
        
        parse_dqt(f, len(dqt_data) + 2, metadata)
        
        for i in range(64):
            assert metadata.quantization_tables[0][i] == float(i)

    def test_parse_8bit_table_id_1(self):
        """Test parsing 8-bit quantization table with ID 1."""
        # Table info: precision=0 (8-bit), table_id=1
        table_info = b"\x01"
        quant_values = bytes([50] * 64)
        dqt_data = table_info + quant_values
        
        f = io.BytesIO(dqt_data)
        metadata = JPEGMetadata()
        
        parse_dqt(f, len(dqt_data) + 2, metadata)
        
        for i in range(64):
            assert metadata.quantization_tables[1][i] == 50.0

    def test_parse_16bit_table(self):
        """Test parsing a 16-bit quantization table."""
        # Table info: precision=1 (16-bit), table_id=0
        table_info = b"\x10"
        # 64 16-bit values (big-endian)
        quant_values = b""
        for i in range(64):
            quant_values += bytes([(i * 4) >> 8, (i * 4) & 0xFF])
        dqt_data = table_info + quant_values
        
        f = io.BytesIO(dqt_data)
        metadata = JPEGMetadata()
        
        parse_dqt(f, len(dqt_data) + 2, metadata)
        
        for i in range(64):
            assert metadata.quantization_tables[0][i] == float(i * 4)

    def test_parse_multiple_tables(self):
        """Test parsing multiple quantization tables in one segment."""
        # First table: ID 0
        table0 = b"\x00" + bytes([10] * 64)
        # Second table: ID 1
        table1 = b"\x01" + bytes([20] * 64)
        dqt_data = table0 + table1
        
        f = io.BytesIO(dqt_data)
        metadata = JPEGMetadata()
        
        parse_dqt(f, len(dqt_data) + 2, metadata)
        
        assert all(v == 10.0 for v in metadata.quantization_tables[0])
        assert all(v == 20.0 for v in metadata.quantization_tables[1])


class TestParseDht:
    """Tests for parse_dht function."""

    def test_parse_dc_table(self):
        """Test parsing a simple DC Huffman table."""
        # Table info: class=0 (DC), table_id=0
        table_info = b"\x00"
        # Code counts: 1 code of length 1, 1 code of length 2, rest are 0
        code_counts = bytes([1, 1] + [0] * 14)
        # Symbols: symbol 0 for 1-bit code, symbol 1 for 2-bit code
        symbols = b"\x00\x01"
        dht_data = table_info + code_counts + symbols
        
        f = io.BytesIO(dht_data)
        metadata = JPEGMetadata()
        
        parse_dht(f, len(dht_data) + 2, metadata)
        
        dc_table = metadata.huffman_tables.dc_tables[0]
        # 1-bit code 0 -> symbol 0
        assert dc_table[(1, 0)] == 0
        # 2-bit code 2 (binary 10) -> symbol 1
        assert dc_table[(2, 2)] == 1

    def test_parse_ac_table(self):
        """Test parsing a simple AC Huffman table."""
        # Table info: class=1 (AC), table_id=0
        table_info = b"\x10"
        # Code counts: 2 codes of length 2
        code_counts = bytes([0, 2] + [0] * 14)
        # Symbols
        symbols = b"\x00\x01"
        dht_data = table_info + code_counts + symbols
        
        f = io.BytesIO(dht_data)
        metadata = JPEGMetadata()
        
        parse_dht(f, len(dht_data) + 2, metadata)
        
        ac_table = metadata.huffman_tables.ac_tables[0]
        # 2-bit codes: 00 -> symbol 0, 01 -> symbol 1
        assert ac_table[(2, 0)] == 0
        assert ac_table[(2, 1)] == 1

    def test_parse_dc_table_id_1(self):
        """Test parsing DC table with ID 1."""
        # Table info: class=0 (DC), table_id=1
        table_info = b"\x01"
        code_counts = bytes([1] + [0] * 15)
        symbols = b"\x05"
        dht_data = table_info + code_counts + symbols
        
        f = io.BytesIO(dht_data)
        metadata = JPEGMetadata()
        
        parse_dht(f, len(dht_data) + 2, metadata)
        
        dc_table = metadata.huffman_tables.dc_tables[1]
        assert dc_table[(1, 0)] == 5

    def test_parse_ac_table_id_1(self):
        """Test parsing AC table with ID 1."""
        # Table info: class=1 (AC), table_id=1
        table_info = b"\x11"
        code_counts = bytes([0, 0, 1] + [0] * 13)  # One 3-bit code
        symbols = b"\x11"
        dht_data = table_info + code_counts + symbols
        
        f = io.BytesIO(dht_data)
        metadata = JPEGMetadata()
        
        parse_dht(f, len(dht_data) + 2, metadata)
        
        ac_table = metadata.huffman_tables.ac_tables[1]
        assert ac_table[(3, 0)] == 0x11

    def test_parse_multiple_tables(self):
        """Test parsing multiple Huffman tables in one segment."""
        # DC table 0
        dc0 = b"\x00" + bytes([1] + [0] * 15) + b"\x00"
        # AC table 0
        ac0 = b"\x10" + bytes([1] + [0] * 15) + b"\x01"
        dht_data = dc0 + ac0
        
        f = io.BytesIO(dht_data)
        metadata = JPEGMetadata()
        
        parse_dht(f, len(dht_data) + 2, metadata)
        
        assert metadata.huffman_tables.dc_tables[0][(1, 0)] == 0
        assert metadata.huffman_tables.ac_tables[0][(1, 0)] == 1


class TestParseSof0:
    """Tests for parse_sof0 function."""

    def test_parse_standard_sof0(self):
        """Test parsing a standard SOF0 segment (YCbCr image)."""
        sof0_data = (
            b"\x08"      # Precision: 8 bits
            b"\x01\x00"  # Height: 256
            b"\x01\x80"  # Width: 384
            b"\x03"      # Number of components: 3
            # Component 1 (Y): ID=1, sampling=2x2, quant_table=0
            b"\x01\x22\x00"
            # Component 2 (Cb): ID=2, sampling=1x1, quant_table=1
            b"\x02\x11\x01"
            # Component 3 (Cr): ID=3, sampling=1x1, quant_table=1
            b"\x03\x11\x01"
        )
        f = io.BytesIO(sof0_data)
        metadata = JPEGMetadata()
        
        parse_sof0(f, len(sof0_data) + 2, metadata)
        
        assert metadata.sof_info.precision == 8
        assert metadata.sof_info.height == 256
        assert metadata.sof_info.width == 384
        
        # Component Y (index 0)
        assert metadata.sof_info.components[0].horizontal_sampling == 2
        assert metadata.sof_info.components[0].vertical_sampling == 2
        assert metadata.sof_info.components[0].quantization_table_id == 0
        
        # Component Cb (index 1)
        assert metadata.sof_info.components[1].horizontal_sampling == 1
        assert metadata.sof_info.components[1].vertical_sampling == 1
        assert metadata.sof_info.components[1].quantization_table_id == 1
        
        # Component Cr (index 2)
        assert metadata.sof_info.components[2].horizontal_sampling == 1
        assert metadata.sof_info.components[2].vertical_sampling == 1
        assert metadata.sof_info.components[2].quantization_table_id == 1
        
        # Max sampling factors
        assert metadata.sof_info.max_horizontal_sampling == 2
        assert metadata.sof_info.max_vertical_sampling == 2

    def test_parse_sof0_no_subsampling(self):
        """Test parsing SOF0 with no chroma subsampling (4:4:4)."""
        sof0_data = (
            b"\x08"      # Precision: 8 bits
            b"\x00\x64"  # Height: 100
            b"\x00\xC8"  # Width: 200
            b"\x03"      # 3 components
            # All components with 1x1 sampling
            b"\x01\x11\x00"
            b"\x02\x11\x01"
            b"\x03\x11\x01"
        )
        f = io.BytesIO(sof0_data)
        metadata = JPEGMetadata()
        
        parse_sof0(f, len(sof0_data) + 2, metadata)
        
        assert metadata.sof_info.height == 100
        assert metadata.sof_info.width == 200
        assert metadata.sof_info.max_horizontal_sampling == 1
        assert metadata.sof_info.max_vertical_sampling == 1

    def test_parse_sof0_grayscale(self):
        """Test parsing SOF0 for a grayscale image."""
        sof0_data = (
            b"\x08"      # Precision: 8 bits
            b"\x00\x20"  # Height: 32
            b"\x00\x20"  # Width: 32
            b"\x01"      # 1 component
            b"\x01\x11\x00"  # Y component only
        )
        f = io.BytesIO(sof0_data)
        metadata = JPEGMetadata()
        
        parse_sof0(f, len(sof0_data) + 2, metadata)
        
        assert metadata.sof_info.height == 32
        assert metadata.sof_info.width == 32
        assert metadata.sof_info.components[0].horizontal_sampling == 1
        assert metadata.sof_info.components[0].vertical_sampling == 1


class TestParseSos:
    """Tests for parse_sos function."""

    def test_parse_standard_sos(self):
        """Test parsing a standard SOS segment."""
        sos_data = (
            b"\x03"      # Number of components: 3
            # Component 1: DC table 0, AC table 0
            b"\x01\x00"
            # Component 2: DC table 1, AC table 1
            b"\x02\x11"
            # Component 3: DC table 1, AC table 1
            b"\x03\x11"
            # Spectral selection and approximation
            b"\x00\x3F\x00"
        )
        f = io.BytesIO(sos_data)
        metadata = JPEGMetadata()
        
        parse_sos(f, len(sos_data) + 2, metadata)
        
        # Component Y (index 0): DC=0, AC=0
        assert metadata.table_mapping[0] == (0, 0)
        # Component Cb (index 1): DC=1, AC=1
        assert metadata.table_mapping[1] == (1, 1)
        # Component Cr (index 2): DC=1, AC=1
        assert metadata.table_mapping[2] == (1, 1)

    def test_parse_sos_grayscale(self):
        """Test parsing SOS for grayscale image."""
        sos_data = (
            b"\x01"      # 1 component
            b"\x01\x00"  # Component 1: DC=0, AC=0
            b"\x00\x3F\x00"
        )
        f = io.BytesIO(sos_data)
        metadata = JPEGMetadata()
        
        parse_sos(f, len(sos_data) + 2, metadata)
        
        assert metadata.table_mapping[0] == (0, 0)

    def test_parse_sos_mixed_tables(self):
        """Test parsing SOS with mixed table assignments."""
        sos_data = (
            b"\x03"      # 3 components
            b"\x01\x01"  # Component 1: DC=0, AC=1
            b"\x02\x10"  # Component 2: DC=1, AC=0
            b"\x03\x11"  # Component 3: DC=1, AC=1
            b"\x00\x3F\x00"
        )
        f = io.BytesIO(sos_data)
        metadata = JPEGMetadata()
        
        parse_sos(f, len(sos_data) + 2, metadata)
        
        assert metadata.table_mapping[0] == (0, 1)
        assert metadata.table_mapping[1] == (1, 0)
        assert metadata.table_mapping[2] == (1, 1)


class TestBrokenJpegFile:
    """Tests for handling broken/malformed JPEG files."""

    def test_truncated_file_during_marker_read(self):
        """Test handling truncated file during marker reading."""
        # Only SOI marker, then EOF
        broken_data = b"\xFF\xD8"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(broken_data)
            temp_path = f.name
        
        try:
            metadata = marker_detector(temp_path)
            # Should return metadata without crashing
            assert metadata is not None
        finally:
            os.unlink(temp_path)

    def test_truncated_segment_length(self):
        """Test handling truncated segment length field."""
        # SOI + APP0 marker but incomplete length
        broken_data = b"\xFF\xD8\xFF\xE0\x00"  # Missing second byte of length
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(broken_data)
            temp_path = f.name
        
        try:
            with pytest.raises(IOError):
                marker_detector(temp_path)
        finally:
            os.unlink(temp_path)

    def test_truncated_segment_data(self):
        """Test handling truncated segment data."""
        # SOI + DQT marker with length=67 but only partial data
        broken_data = (
            b"\xFF\xD8"  # SOI
            b"\xFF\xDB"  # DQT marker
            b"\x00\x43"  # Length: 67 (1 byte info + 64 bytes table + 2 bytes length)
            b"\x00"      # Table info
            + bytes([0] * 30)  # Only 30 bytes instead of 64
        )
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(broken_data)
            temp_path = f.name
        
        try:
            with pytest.raises(IOError):
                marker_detector(temp_path)
        finally:
            os.unlink(temp_path)

    def test_empty_file(self):
        """Test handling empty file."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            temp_path = f.name
        
        try:
            metadata = marker_detector(temp_path)
            # Should return default metadata without crashing
            assert metadata is not None
            assert metadata.sof_info.width == 0
            assert metadata.sof_info.height == 0
        finally:
            os.unlink(temp_path)

    def test_no_soi_marker(self):
        """Test handling file without SOI marker."""
        # Random data without valid JPEG structure
        broken_data = b"\x00\x01\x02\x03\x04\x05"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(broken_data)
            temp_path = f.name
        
        try:
            metadata = marker_detector(temp_path)
            # Should return default metadata
            assert metadata is not None
        finally:
            os.unlink(temp_path)

    def test_invalid_marker_value(self):
        """Test handling invalid marker values (0xFF followed by 0xFF)."""
        # 0xFF 0xFF is padding, should be skipped
        broken_data = b"\xFF\xD8\xFF\xFF\xFF\xD9"  # SOI + padding + EOI
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(broken_data)
            temp_path = f.name
        
        try:
            metadata = marker_detector(temp_path)
            assert metadata is not None
        finally:
            os.unlink(temp_path)

    def test_read_u8_truncated(self):
        """Test read_u8 with truncated input."""
        f = io.BytesIO(b"")
        with pytest.raises(IOError):
            read_u8(f)

    def test_read_u16_truncated(self):
        """Test read_u16 with truncated input."""
        f = io.BytesIO(b"\x00")  # Only 1 byte
        with pytest.raises(IOError):
            read_u16(f)

    def test_corrupted_dqt_table_id(self):
        """Test handling DQT with invalid table ID (> 3)."""
        # Table info with table_id=5 (invalid but shouldn't crash)
        dqt_data = b"\x05" + bytes([16] * 64)
        
        f = io.BytesIO(dqt_data)
        metadata = JPEGMetadata()
        
        # Should not crash, but may write to invalid index
        # This tests defensive coding - implementation may vary
        try:
            parse_dqt(f, len(dqt_data) + 2, metadata)
        except (IndexError, KeyError):
            pass  # Expected if no bounds checking


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_read_u8(self):
        """Test read_u8 function."""
        f = io.BytesIO(b"\x42")
        assert read_u8(f) == 0x42

    def test_read_u8_zero(self):
        """Test read_u8 with zero value."""
        f = io.BytesIO(b"\x00")
        assert read_u8(f) == 0

    def test_read_u8_max(self):
        """Test read_u8 with max value."""
        f = io.BytesIO(b"\xFF")
        assert read_u8(f) == 255

    def test_read_u16(self):
        """Test read_u16 function (big-endian)."""
        f = io.BytesIO(b"\x01\x00")
        assert read_u16(f) == 256

    def test_read_u16_zero(self):
        """Test read_u16 with zero."""
        f = io.BytesIO(b"\x00\x00")
        assert read_u16(f) == 0

    def test_read_u16_max(self):
        """Test read_u16 with max value."""
        f = io.BytesIO(b"\xFF\xFF")
        assert read_u16(f) == 65535

    def test_read_u16_big_endian(self):
        """Test read_u16 is big-endian."""
        f = io.BytesIO(b"\x12\x34")
        assert read_u16(f) == 0x1234

