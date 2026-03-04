def get_color_for_temperature(degrees):
    # 41 and higher
    if degrees >= 41:
        return 0x9A1B1E
    # 36 to 40
    elif degrees >= 36:
        return 0xC12026
    # 30 to 35
    elif degrees >= 30:
        return 0xEE2D29
    # 25 to 29
    elif degrees >= 25:
        return 0xEB5038
    # 21 to 24
    elif degrees >= 21:
        return 0xF26A30
    # 19 to 20
    elif degrees >= 19:
        return 0xF68A1F
    # 17 to 18
    elif degrees >= 17:
        return 0xFAA31A
    # 15 to 16
    elif degrees >= 15:
        return 0xFBB616
    # 13 to 14
    elif degrees >= 13:
        return 0xFCC90D
    # 11 to 12
    elif degrees >= 11:
        return 0xFEDB00
    # 9 to 10
    elif degrees >= 9:
        return 0xD0D73E
    # 7 to 8
    elif degrees >= 7:
        return 0xAFD251
    # 5 to 6
    elif degrees >= 5:
        return 0x9FCD80
    # 3 to 4
    elif degrees >= 3:
        return 0xAAD6AE
    # 1 to 2
    elif degrees >= 1:
        return 0xAEDCD8
    # 0 to -2
    elif degrees >= -2:
        return 0x51BFED
    # -3 to -5
    elif degrees >= -5:
        return 0x43A3D9
    # -6 to -10
    elif degrees >= -10:
        return 0x3789C6
    # -11 to -15
    elif degrees >= -15:
        return 0x2374B6
    # -16 to -22
    elif degrees >= -22:
        return 0x0262A9
    # -23 and lower
    elif degrees <= -23:
        return 0x1F4799
    # Invalid
    else:
        return 0xD5D0CD

def get_color_for_uv(index):
    if index < 3:
        return 0x71B466
    elif index < 6:
        return 0xF8E71C
    elif index < 8:
        return 0xFF950C
    elif index < 11:
        return 0xD72921
    else:
        return 0x6600E0

def get_color_for_humidity(percentage):
    if percentage <= 20:
        return 0xDC3522
    elif percentage <= 40:
        return 0xFF8C00
    elif percentage <= 60:
        return 0x4CAF50
    elif percentage <= 80:
        return 0x2196F3
    elif percentage <= 100:
        return 0x1E88E5
    else:
        return 0xD5D0CD

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
        return 0x808080
    # 1-10% - Very light rain chance
    elif percentage <= 10:
        return 0x969696
    # 11-25% - Light rain chance
    elif percentage <= 25:
        return 0xB4C8DC
    # 26-40% - Moderate rain chance
    elif percentage <= 40:
        return 0xA0BEE6
    # 41-60% - High rain chance
    elif percentage <= 60:
        return 0x8CB4F0
    # 61-80% - Very high rain chance
    elif percentage <= 80:
        return 0x78AAFA
    # 81-95% - Heavy rain chance
    elif percentage <= 95:
        return 0x64A0FF
    # 96-100% - Certain rain
    elif percentage <= 100:
        return 0x5096FF
    # Invalid values
    else:
        return 0xD5D0CD

def get_color_for_precip_rate(rate_mmh):
    if rate_mmh is None:
        return 0xD5D0CD
    if rate_mmh > 32:
        return 0xB30000
    elif rate_mmh >= 16:
        return 0xFE0000
    elif rate_mmh >= 8:
        return 0xFE9800
    elif rate_mmh >= 4:
        return 0xFECB00
    elif rate_mmh >= 2:
        return 0x00A300
    elif rate_mmh >= 1:
        return 0x0CBCFE
    elif rate_mmh >= 0.5:
        return 0x3265FE
    elif rate_mmh >= 0:
        return 0x0000FE
    else:
        return 0xD5D0CD

def get_color_for_wind_speed(wind_speed_ms):
    """
    Get color for wind speed based on Beaufort scale.
    Wind speed should be in meters per second (m/s).
    Returns (r, g, b) tuple based on Beaufort scale colors.
    """
    if wind_speed_ms is None:
        return 0xD5D0CD
    
    # Beaufort scale 12: Hurricane-force (≥ 32.7 m/s)
    if wind_speed_ms >= 32.7:
        return 0xD5102D
    
    # Beaufort scale 11: Violent storm (28.5-32.6 m/s)
    elif wind_speed_ms >= 28.5:
        return 0xED2912
    
    # Beaufort scale 10: Storm (24.5-28.4 m/s)
    elif wind_speed_ms >= 24.5:
        return 0xED6312
    
    # Beaufort scale 9: Strong/severe gale (20.8-24.4 m/s)
    elif wind_speed_ms >= 20.8:
        return 0xED8F12
    
    # Beaufort scale 8: Gale (17.2-20.7 m/s)
    elif wind_speed_ms >= 17.2:
        return 0xEDC212
    
    # Beaufort scale 7: Moderate gale (13.9-17.1 m/s)
    elif wind_speed_ms >= 13.9:
        return 0xDAED12
    
    # Beaufort scale 6: Strong breeze (10.8-13.8 m/s)
    elif wind_speed_ms >= 10.8:
        return 0xA4ED12
    
    # Beaufort scale 5: Fresh breeze (8-10.7 m/s)
    elif wind_speed_ms >= 8.0:
        return 0x73ED12
    
    # Beaufort scale 4: Moderate breeze (5.5-7.9 m/s)
    elif wind_speed_ms >= 5.5:
        return 0x6FF46F
    
    # Beaufort scale 3: Gentle breeze (3.4-5.4 m/s)
    elif wind_speed_ms >= 3.4:
        return 0x96F7B4
    
    # Beaufort scale 2: Light breeze (1.6-3.3 m/s)
    elif wind_speed_ms >= 1.6:
        return 0x96F7DC
    
    # Beaufort scale 1: Light air (0.3-1.5 m/s)
    elif wind_speed_ms >= 0.3:
        return 0xAEF1F9
    
    # Beaufort scale 0: Calm (< 0.3 m/s)
    elif wind_speed_ms >= 0:
        return 0xFFFFFF
    
    # Invalid negative values
    else:
        return 0xD5D0CD

def get_color_for_beaufort_scale(beaufort_number):
    """
    Get color for Beaufort scale number based on the official Beaufort scale colors.
    Beaufort number should be 0-12 (or 13-17 for extended scale).
    Returns (r, g, b) tuple based on Beaufort scale colors from Wikipedia.
    """
    if beaufort_number is None or beaufort_number < 0:
        return 0xD5D0CD
    
    # Beaufort scale colors from Wikipedia
    if beaufort_number == 0:
        return 0xFFFFFF
    elif beaufort_number == 1:
        return 0xAEF1F9
    elif beaufort_number == 2:
        return 0x96F7DC
    elif beaufort_number == 3:
        return 0x96F7B4
    elif beaufort_number == 4:
        return 0x6FF46F
    elif beaufort_number == 5:
        return 0x73ED12
    elif beaufort_number == 6:
        return 0xA4ED12
    elif beaufort_number == 7:
        return 0xDAED12
    elif beaufort_number == 8:
        return 0xEDC212
    elif beaufort_number == 9:
        return 0xED8F12
    elif beaufort_number == 10:
        return 0xED6312
    elif beaufort_number == 11:
        return 0xED2912
    elif beaufort_number >= 12:
        return 0xD5102D
    else:
        return 0xD5D0CD
