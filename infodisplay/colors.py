def get_color_for_temperature(degrees):
    # 41 and higher
    if degrees >= 41:
        return 0x98C3  # (154, 27, 30)
    # 36 to 40
    elif degrees >= 36:
        return 0xC104  # (193, 32, 38)
    # 30 to 35
    elif degrees >= 30:
        return 0xE965  # (238, 45, 41)
    # 25 to 29
    elif degrees >= 25:
        return 0xEA87  # (235, 80, 56)
    # 21 to 24
    elif degrees >= 21:
        return 0xF346  # (242, 106, 48)
    # 19 to 20
    elif degrees >= 19:
        return 0xF443  # (246, 138, 31)
    # 17 to 18
    elif degrees >= 17:
        return 0xFD03  # (250, 163, 26)
    # 15 to 16
    elif degrees >= 15:
        return 0xFDA2  # (251, 182, 22)
    # 13 to 14
    elif degrees >= 13:
        return 0xFE41  # (252, 201, 13)
    # 11 to 12
    elif degrees >= 11:
        return 0xFEC0  # (254, 219, 0)
    # 9 to 10
    elif degrees >= 9:
        return 0xD6A7  # (208, 215, 62)
    # 7 to 8
    elif degrees >= 7:
        return 0xAE8A  # (175, 210, 81)
    # 5 to 6
    elif degrees >= 5:
        return 0x9E70  # (159, 205, 128)
    # 3 to 4
    elif degrees >= 3:
        return 0xAEB5  # (170, 214, 174)
    # 1 to 2
    elif degrees >= 1:
        return 0xAEFB  # (174, 220, 216)
    # 0 to -2
    elif degrees >= -2:
        return 0x55FD  # (81, 191, 237)
    # -3 to -5
    elif degrees >= -5:
        return 0x451B  # (67, 163, 217)
    # -6 to -10
    elif degrees >= -10:
        return 0x3458  # (55, 137, 198)
    # -11 to -15
    elif degrees >= -15:
        return 0x23B6  # (35, 116, 182)
    # -16 to -22
    elif degrees >= -22:
        return 0x0315  # (2, 98, 169)
    # -23 and lower
    elif degrees <= -23:
        return 0x1A33  # (31, 71, 153)
    # Invalid
    else:
        return 0xD699  # (213, 208, 205)

def get_color_for_uv(index):
    if index < 3:
        return 0x75AC  # (113, 180, 102)
    elif index < 6:
        return 0xFF23  # (248, 231, 28)
    elif index < 8:
        return 0xFCA1  # (255, 149, 12)
    elif index < 11:
        return 0xD144  # (215, 41, 33)
    else:
        return 0x601C  # (102, 0, 224)

def get_color_for_humidity(percentage):
    if percentage <= 20:
        return 0xD9A4  # (220, 53, 34)
    elif percentage <= 40:
        return 0xFC60  # (255, 140, 0)
    elif percentage <= 60:
        return 0x4D6A  # (76, 175, 80)
    elif percentage <= 80:
        return 0x24BE  # (33, 150, 243)
    elif percentage <= 100:
        return 0x1C5C  # (30, 136, 229)
    else:
        return 0xD699  # (213, 208, 205)

def get_humidity_category_letter(percentage):
    if percentage <= 20:
        return 'VD'  # Very Dry
    elif percentage <= 40:
        return 'DR'  # Dry
    elif percentage <= 60:
        return 'OK'  # Comfortable
    elif percentage <= 80:
        return 'MU'  # Muggy/Humid
    elif percentage <= 100:
        return 'VH'  # Very Humid / Near Saturation
    else:
        return '??'

def get_color_for_rain_percentage(percentage):
    # 0% - No rain
    if percentage == 0:
        return 0x8410  # (128, 128, 128) Light gray - no rain
    # 1-10% - Very light rain chance
    elif percentage <= 10:
        return 0x94B2  # (150, 150, 150) Light gray
    # 11-25% - Light rain chance
    elif percentage <= 25:
        return 0xB65B  # (180, 200, 220) Very light blue-gray
    # 26-40% - Moderate rain chance
    elif percentage <= 40:
        return 0xA5FC  # (160, 190, 230) Light blue-gray
    # 41-60% - High rain chance
    elif percentage <= 60:
        return 0x8DBE  # (140, 180, 240) Light blue
    # 61-80% - Very high rain chance
    elif percentage <= 80:
        return 0x7D5F  # (120, 170, 250) Medium light blue
    # 81-95% - Heavy rain chance
    elif percentage <= 95:
        return 0x651F  # (100, 160, 255) Light blue
    # 96-100% - Certain rain
    elif percentage <= 100:
        return 0x54BF  # (80, 150, 255) Light blue
    # Invalid values
    else:
        return 0xD699  # (213, 208, 205) Default gray for invalid values

def get_color_for_precip_rate(rate_mmh):
    if rate_mmh is None:
        return 0xD699  # (213, 208, 205)
    if rate_mmh > 32:
        return 0xB000  # (179, 0, 0)
    elif rate_mmh >= 16:
        return 0xF800  # (254, 0, 0)
    elif rate_mmh >= 8:
        return 0xFCC0  # (254, 152, 0)
    elif rate_mmh >= 4:
        return 0xFE40  # (254, 203, 0)
    elif rate_mmh >= 2:
        return 0x0500  # (0, 163, 0)
    elif rate_mmh >= 1:
        return 0x0DFF  # (12, 188, 254)
    elif rate_mmh >= 0.5:
        return 0x333F  # (50, 101, 254)
    elif rate_mmh >= 0:
        return 0x001F  # (0, 0, 254)
    else:
        return 0xD699  # (213, 208, 205)

def get_color_for_wind_speed(wind_speed_ms):
    """
    Get color for wind speed based on Beaufort scale.
    Wind speed should be in meters per second (m/s).
    Returns 16-bit RGB565 hex integer based on Beaufort scale colors.
    """
    if wind_speed_ms is None:
        return 0xD699  # (213, 208, 205) Default gray for invalid values
    
    # Beaufort scale 12: Hurricane-force (≥ 32.7 m/s)
    if wind_speed_ms >= 32.7:
        return 0xD085  # (213, 16, 45) - Dark red
    
    # Beaufort scale 11: Violent storm (28.5-32.6 m/s)
    elif wind_speed_ms >= 28.5:
        return 0xE942  # (237, 41, 18) - Red
    
    # Beaufort scale 10: Storm (24.5-28.4 m/s)
    elif wind_speed_ms >= 24.5:
        return 0xEB02  # (237, 99, 18) - Red-orange
    
    # Beaufort scale 9: Strong/severe gale (20.8-24.4 m/s)
    elif wind_speed_ms >= 20.8:
        return 0xEC62  # (237, 143, 18) - Orange-red
    
    # Beaufort scale 8: Gale (17.2-20.7 m/s)
    elif wind_speed_ms >= 17.2:
        return 0xEE02  # (237, 194, 18) - Orange
    
    # Beaufort scale 7: Moderate gale (13.9-17.1 m/s)
    elif wind_speed_ms >= 13.9:
        return 0xDF62  # (218, 237, 18) - Yellow
    
    # Beaufort scale 6: Strong breeze (10.8-13.8 m/s)
    elif wind_speed_ms >= 10.8:
        return 0xA762  # (164, 237, 18) - Yellow-green
    
    # Beaufort scale 5: Fresh breeze (8-10.7 m/s)
    elif wind_speed_ms >= 8.0:
        return 0x7762  # (115, 237, 18) - Green
    
    # Beaufort scale 4: Moderate breeze (5.5-7.9 m/s)
    elif wind_speed_ms >= 5.5:
        return 0x6FAD  # (111, 244, 111) - Light green
    
    # Beaufort scale 3: Gentle breeze (3.4-5.4 m/s)
    elif wind_speed_ms >= 3.4:
        return 0x97B6  # (150, 247, 180) - Green
    
    # Beaufort scale 2: Light breeze (1.6-3.3 m/s)
    elif wind_speed_ms >= 1.6:
        return 0x97BB  # (150, 247, 220) - Light green
    
    # Beaufort scale 1: Light air (0.3-1.5 m/s)
    elif wind_speed_ms >= 0.3:
        return 0xAF9F  # (174, 241, 249) - Light blue
    
    # Beaufort scale 0: Calm (< 0.3 m/s)
    elif wind_speed_ms >= 0:
        return 0xFFFF  # (255, 255, 255) - White
    
    # Invalid negative values
    else:
        return 0xD699  # (213, 208, 205) Default gray for invalid values

def get_color_for_beaufort_scale(beaufort_number):
    """
    Get color for Beaufort scale number based on the official Beaufort scale colors.
    Beaufort number should be 0-12 (or 13-17 for extended scale).
    Returns 16-bit RGB565 hex integer based on Beaufort scale colors from Wikipedia.
    """
    if beaufort_number is None or beaufort_number < 0:
        return 0xD699  # (213, 208, 205) Default gray for invalid values
    
    # Beaufort scale colors from Wikipedia
    if beaufort_number == 0:
        return 0xFFFF  # (255, 255, 255) - White (Calm)
    elif beaufort_number == 1:
        return 0xAF9F  # (174, 241, 249) - Light air
    elif beaufort_number == 2:
        return 0x97BB  # (150, 247, 220) - Light breeze
    elif beaufort_number == 3:
        return 0x97B6  # (150, 247, 180) - Gentle breeze
    elif beaufort_number == 4:
        return 0x6FAD  # (111, 244, 111) - Moderate breeze
    elif beaufort_number == 5:
        return 0x7762  # (115, 237, 18) - Fresh breeze
    elif beaufort_number == 6:
        return 0xA762  # (164, 237, 18) - Strong breeze
    elif beaufort_number == 7:
        return 0xDF62  # (218, 237, 18) - Moderate gale
    elif beaufort_number == 8:
        return 0xEE02  # (237, 194, 18) - Gale
    elif beaufort_number == 9:
        return 0xEC62  # (237, 143, 18) - Strong/severe gale
    elif beaufort_number == 10:
        return 0xEB02  # (237, 99, 18) - Storm
    elif beaufort_number == 11:
        return 0xE942  # (237, 41, 18) - Violent storm
    elif beaufort_number == 12:
        return 0xD085  # (213, 16, 45) - Hurricane-force
    elif beaufort_number >= 13:  # Extended scale (13-17)
        return 0xD085  # (213, 16, 45) - Same as hurricane-force for extended scale
    else:
        return 0xD699  # (213, 208, 205) Default gray for invalid values
