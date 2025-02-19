import os
import sys
import ffmpeg
import struct
import time

def build_intermediates(goodfile, outfile_prefix):
    sample_h264 = f"{outfile_prefix}-headers.h264"
    sample_stat_h264 = f"{outfile_prefix}-stat.mp4"
    sample_aac = f"{outfile_prefix}-headers.aac"
    sample_nals = f"{outfile_prefix}-nals.txt"

    if not os.path.exists(sample_h264):
        ffmpeg.input(goodfile).output(sample_h264, vframes=1, bsf='h264_mp4toannexb').run()
    if not os.path.exists(sample_stat_h264):
        ffmpeg.input(goodfile).output(sample_stat_h264, t=20, an=None).run()
    if not os.path.exists(sample_nals):
        with open(sample_nals, 'w') as f:
            f.write(ffmpeg.probe(sample_stat_h264, select_streams='0', show_packets=True, show_data=True))
    if not os.path.exists(sample_aac):
        ffmpeg.input(goodfile).output(sample_aac, t=1, f='adts').run()

def main():
    if len(sys.argv) < 4:
        print(f"Usage:\n{sys.argv[0]} <good_file.mp4> <bad_file.mp4> <output_prefix>")
        return

    goodfile, badfile, outfile_prefix = sys.argv[1:4]
    sample_h264 = f"{outfile_prefix}-headers.h264"
    sample_nals = f"{outfile_prefix}-nals.txt"
    out_video = f"{outfile_prefix}-out-video.h264"
    out_audio = f"{outfile_prefix}-out-audio.raw"

    print("Build intermediates...")
    build_intermediates(goodfile, outfile_prefix)

    print("Opening files...")
    with open(badfile, 'rb') as bfile, open(sample_h264, 'rb') as vhead, open(sample_nals, 'r') as nals, \
         open(out_video, 'wb') as vout, open(out_audio, 'wb') as aout:
        
        header = vhead.read(0x100)
        header = header.split(b'\x00\x00\x01')[0] + b'\x00\x00\x01'
        
        vout.write(header)

        nals_map = [{'min': 0xFFFFFF, 'max': 0x0, 'id': i, 'bytes': {}, 'printbytes': {}} for i in range(32)]
        
        buf = ""
        for line in nals:
            if line.startswith("0.......: "):
                buf += line[10:50]
                continue
            if line.startswith("[/PACKET]") and buf:
                buf = ''.join(filter(str.isalnum, buf))
                while buf:
                    size = int(buf[:8], 16)
                    if len(buf) >= size * 2 + 8:
                        type_ = int(buf[8:10], 16) & 0b11111
                        bytes_ = bytes.fromhex(buf[8:14] if type_ == 5 else buf[8:12])
                        n = nals_map[type_]
                        n['min'] = min(n['min'], size)
                        n['max'] = max(n['max'], size)
                        n['bytes'][bytes_] = 1
                        n['printbytes'][buf[8:16]] = 1
                        buf = buf[8 + size * 2:]
                    else:
                        break
                buf = ""

        print("NAL units processed.")
        
        file_data = bfile.read()
        file_pos = 0
        was_key = False
        while file_pos < len(file_data):
            size = struct.unpack('>I', file_data[file_pos:file_pos+4])[0]
            header = file_data[file_pos+4]
            zerobit = header & 0x80
            type_ = header & 0b11111
            if zerobit == 0 and nals_map[type_]['max']:
                nextbytes = file_data[file_pos+4:file_pos+7] if type_ == 5 else file_data[file_pos+4:file_pos+6]
                if nextbytes in nals_map[type_]['bytes'] and nals_map[type_]['min'] / 2 <= size <= nals_map[type_]['max'] * 2:
                    print(f"Got! {size} bytes")
                    if was_key:
                        aout.write(file_data[file_pos:file_pos+size+4])
                    if type_ == 5 or was_key:
                        vout.write(b'\x00\x00\x00\x01')
                        vout.write(file_data[file_pos+4:file_pos+size+4])
                        was_key = True
                    file_pos += size + 4
                else:
                    file_pos += 1
            else:
                file_pos += 1

        print(f"Repaired video saved to {out_video}")
        print(f"Repaired audio saved to {out_audio}")

if __name__ == "__main__":
    main()
