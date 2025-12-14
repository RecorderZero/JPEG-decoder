import argparse
from pathlib import Path

from src.jpeg_decoder.image import Image
from src.jpeg_decoder.ppm import to_ppm
from src.jpeg_decoder.decoder import decoder, show_mcu_stage
from src.jpeg_decoder.marker import marker_detector
from src.jpeg_decoder.reader import data_reader

from cal import cal
def main():
    parser = argparse.ArgumentParser(description="JPEG Decoder")
    parser.add_argument("path", help="Path to the JPEG file to decode")

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("marker", help="Detect and display JPEG markers in the file")
    subparsers.add_parser("reader", help="Decode and display data segments from the JPEG file")
    subparsers.add_parser("ppm", help="Output the decoded image as a PPM file")

    parser_mcu = subparsers.add_parser("mcu", help="Show MCU decoding stages")
    parser_mcu.add_argument("y", help="Y coordinate of the MCU, top to down")
    parser_mcu.add_argument("x", help="X coordinate of the MCU, left to right")

    args = parser.parse_args()

    jpeg_path = Path(args.path)
    f = open(jpeg_path, "rb")
    
    if args.command == "marker":
        marker_detector(jpeg_path)
    elif args.command == "reader":
        data_reader(jpeg_path)
    elif args.command == "ppm":
        img = decoder(jpeg_path)
        to_ppm(img, "out.ppm")
    elif args.command == "mcu":
        y = int(args.y)
        x = int(args.x)
        print(y, x)
        show_mcu_stage(jpeg_path, y, x)
    else:
        # Default action: decode and output PPM
        img = decoder(jpeg_path)
        to_ppm(img, "out.ppm")
        cal(jpeg_path)

    return 0

if __name__ == "__main__":
    main()