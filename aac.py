import sys
import struct
import time
import pydub
from pyaacdec import NeAACDec, NeAACDecFrameInfo

def write_wave_header(out_file, channels, samplerate):
    header = struct.pack('<4sI4s4sIHHIIHH4sI',
                         b'RIFF',
                         0xFFFFFFFF,
                         b'WAVE',
                         b'fmt ',
                         16,
                         1,
                         channels,
                         samplerate,
                         samplerate * channels * 2,
                         channels * 2,
                         16,
                         b'data',
                         0xFFFFFFFF)
    out_file.write(header)

def main():
    if len(sys.argv) < 3:
        print(f"Usage:\n{sys.argv[0]} <good_file.aac> <bad_file.aac>\n")
        return

    goodfile, badfile = sys.argv[1], sys.argv[2]

    out_pcm_filename = f"{badfile}-pure.wav"
    out_aac_filename = f"{badfile}-pure-adts.aac"

    with open(goodfile, 'rb') as puru, open(badfile, 'rb') as pure, \
         open(out_pcm_filename, 'wb') as out_pcm, open(out_aac_filename, 'wb') as out_aac:
        
        adts = puru.read(7)
        blocksize = 10000000
        buf_start = bytearray(blocksize)
        tmp = bytearray(100000)
        good_aac = bytearray(10000)
        good_pcm = bytearray(100000)

        puru.seek(0, 0)
        samplerate, channels = NeAACDec.get_header_info(adts)
        print(f"Using parameters:\nsamplerate: {samplerate}, channels: {channels}")

        write_wave_header(out_pcm, channels, samplerate)

        decoder = NeAACDec()
        decoder.init(adts, samplerate, channels)
        frame = NeAACDecFrameInfo()

        size = 0
        good_aac_size = 0
        good_pcm_size = 0
        last_time = time.time()

        while True:
            if size < 8192 and not pure.closed:
                if size:
                    buf_start[:size] = buf_start[:size]
                buf = buf_start
                read = pure.readinto(memoryview(buf)[size:])
                size += read

            if size <= 0:
                break

            ss = min(8192, size)
            tmp[:7] = adts
            tmp[3] = (tmp[3] & 0xFC) | (ss >> 11)
            tmp[4] = ss >> 3
            tmp[5] = (tmp[5] & 0x1F) | (ss << 5)
            tmp[7:ss + 7] = buf[:ss]

            samples, frame = decoder.decode(tmp[:ss + 7])

            if frame.bytesconsumed > 0:
                if frame.bytesconsumed > 30:
                    if frame.samples > 0:
                        if good_pcm_size:
                            out_pcm.write(good_pcm[:good_pcm_size * 2])
                            out_pcm.flush()

                        good_pcm_size = frame.samples
                        good_pcm[:frame.samples * 2] = samples

                    ss = frame.bytesconsumed
                    tmp[:7] = adts
                    tmp[3] = (tmp[3] & 0xFC) | (ss >> 11)
                    tmp[4] = ss >> 3
                    tmp[5] = (tmp[5] & 0x1F) | (ss << 5)

                    print(f"Consumed {frame.bytesconsumed}, got samples: {frame.samples}, {size} bytes remain")

                    if good_aac_size:
                        out_aac.write(good_aac[:good_aac_size])
                    
                    good_aac_size = ss
                    good_aac[:ss] = tmp[:ss]

                buf = buf[frame.bytesconsumed - 7:]
                size -= frame.bytesconsumed - 7
            else:
                good_aac_size = 0
                now = time.time()

                if now - last_time:
                    print(f"Consumed 0, position: {pure.tell() - size}")
                    last_time = now

                decoder.close()
                decoder = NeAACDec()
                decoder.init(adts, samplerate, channels)

                buf = buf[1:]
                size -= 1

                if size <= 0:
                    break

        decoder.close()
        print("Completed")

if __name__ == "__main__":
    main()
