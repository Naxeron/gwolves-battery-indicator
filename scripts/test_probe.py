import hid
import time

VID = 0x33e4
PID = 0x5807 # HSK Pro 4K Receiver

# Freq mappings
FREQ_TO_BYTE = {
    125: 8,
    250: 4,
    500: 2,
    1000: 1,
    2000: 32,
    4000: 64,
    8000: 128
}

def query(dev):
    query_buf = [0] * 65
    query_buf[0] = 0
    query_buf[3] = 2
    query_buf[4] = 2
    query_buf[5] = 1
    query_buf[6] = 0x80
    query_buf[7] = 1 # wireless
    dev.send_feature_report(query_buf)
    time.sleep(0.05)
    resp = dev.get_feature_report(0, 65)
    if resp and len(resp) >= 10:
        shifted = resp[1] == 161
        val = resp[9] if shifted else resp[8]
        val_freq = resp[8] if shifted else resp[7]
        print(f"Current Rate Byte: {val_freq} (Response: {resp[:10]})")
    else:
        print("No response")

def set_rate(dev, cmd_id, wireless_flag, rate_byte, other_index=8):
    buf = [0] * 65
    buf[0] = 0
    buf[3] = 2
    buf[4] = 2
    buf[5] = 1
    buf[6] = cmd_id
    buf[7] = wireless_flag
    buf[other_index] = rate_byte
    
    print(f"Trying cmd={cmd_id}, flag={wireless_flag}, idx[{other_index}]={rate_byte}")
    dev.send_feature_report(buf)
    time.sleep(0.1)
    query(dev)

def main():
    devs = [d for d in hid.enumerate(VID) if d['product_id'] == PID]
    if not devs:
        print("HSK Pro 4K not found")
        return
    
    dev = hid.device()
    dev.open_path(devs[0]['path'])
    
    print("Initial State:")
    query(dev)
    
    # Try setting to 500Hz (2)
    # The current `new` protocol logic does: buf[6]=0, buf[7]=1, buf[8]=freq
    set_rate(dev, 0, 1, 2, 8)
    
    # What if it's buf[6]=0x02 ? (sometimes set command is 0x02 or 0x81)
    set_rate(dev, 2, 1, 2, 8)
    
    # What if wireless flag is 0?
    set_rate(dev, 0, 0, 2, 8)
    
    # What if the rate byte is at buf[9]?
    set_rate(dev, 0, 1, 2, 9)
    
    print("Testing OLD protocol format - 4000Hz (64):")
    buf_old = [0] * 65
    buf_old[0] = 0
    buf_old[2] = 2
    buf_old[3] = 2
    buf_old[4] = 0
    buf_old[5] = 64 # 4000Hz
    dev.send_feature_report(buf_old)
    time.sleep(0.1)
    query(dev)
    
    print("Testing OLD protocol format - 1000Hz (1):")
    buf_old[5] = 1 # 1000Hz
    dev.send_feature_report(buf_old)
    time.sleep(0.1)
    query(dev)


if __name__ == "__main__":
    main()
