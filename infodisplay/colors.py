def get_color_for_temperature(degrees):
    # 41 and higher
    if degrees >= 41:
        return (154, 27, 30)
    # 36 to 40
    elif degrees >= 36:
        return (193, 32, 38)
    # 30 to 35
    elif degrees >= 30:
        return (238, 45, 41)
    # 25 to 29
    elif degrees >= 25:
        return (235, 80, 56)
    # 21 to 24
    elif degrees >= 21:
        return (242, 106, 48)
    # 19 to 20
    elif degrees >= 19:
        return (246, 138, 31)
    # 17 to 18
    elif degrees >= 17:
        return (250, 163, 26)
    # 15 to 16
    elif degrees >= 15:
        return (251, 182, 22)
    # 13 to 14
    elif degrees >= 13:
        return (252, 201, 13)
    # 11 to 12
    elif degrees >= 11:
        return (254, 219, 0)
    # 9 to 10
    elif degrees >= 9:
        return (208, 215, 62)
    # 7 to 8
    elif degrees >= 7:
        return (175, 210, 81)
    # 5 to 6
    elif degrees >= 5:
        return (159, 205, 128)
    # 3 to 4
    elif degrees >= 3:
        return (170, 214, 174)
    # 1 to 2
    elif degrees >= 1:
        return (174, 220, 216)
    # 0 to -2
    elif degrees >= -2:
        return (81, 191, 237)
    # -3 to -5
    elif degrees >= -5:
        return (67, 163, 217)
    # -6 to -10
    elif degrees >= -10:
        return (55, 137, 198)
    # -11 to -15
    elif degrees >= -15:
        return (35, 116, 182)
    # -16 to -22
    elif degrees >= -22:
        return (2, 98, 169)
    # -23 and lower
    elif degrees <= -23:
        return (31, 71, 153)
    # Invalid
    else:
        return (213, 208, 205)

def get_color_for_uv(index):
    if index < 3:
        return (113, 180, 102)
    elif index < 6:
        return (248, 231, 28)
    elif index < 8:
        return (255, 149, 12)
    elif index < 11:
        return (215, 41, 33)
    else:
        return (102, 0, 224)

def get_color_for_humidity(percentage):
    if percentage <= 20:
        return (220, 53, 34)
    elif percentage <= 40:
        return (255, 140, 0)
    elif percentage <= 60:
        return (76, 175, 80)
    elif percentage <= 80:
        return (33, 150, 243)
    elif percentage <= 100:
        return (30, 136, 229)
    else:
        return (213, 208, 205)

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
        return (128, 128, 128)
    # 1-10% - Very light rain chance
    elif percentage <= 10:
        return (150, 150, 150)
    # 11-25% - Light rain chance
    elif percentage <= 25:
        return (180, 200, 220)
    # 26-40% - Moderate rain chance
    elif percentage <= 40:
        return (160, 190, 230)
    # 41-60% - High rain chance
    elif percentage <= 60:
        return (140, 180, 240)
    # 61-80% - Very high rain chance
    elif percentage <= 80:
        return (120, 170, 250)
    # 81-95% - Heavy rain chance
    elif percentage <= 95:
        return (100, 160, 255)
    # 96-100% - Certain rain
    elif percentage <= 100:
        return (80, 150, 255)
    # Invalid values
    else:
        return (213, 208, 205)

def get_color_for_precip_rate(rate_mmh):
    if rate_mmh is None:
        return (213, 208, 205)
    if rate_mmh > 32:
        return (179, 0, 0)
    elif rate_mmh >= 16:
        return (254, 0, 0)
    elif rate_mmh >= 8:
        return (254, 152, 0)
    elif rate_mmh >= 4:
        return (254, 203, 0)
    elif rate_mmh >= 2:
        return (0, 163, 0)
    elif rate_mmh >= 1:
        return (12, 188, 254)
    elif rate_mmh >= 0.5:
        return (50, 101, 254)
    elif rate_mmh >= 0:
        return (0, 0, 254)
    else:
        return (213, 208, 205)

def get_color_for_wind_speed(wind_speed_ms):
    """
    Get color for wind speed based on Beaufort scale.
    Wind speed should be in meters per second (m/s).
    Returns (r, g, b) tuple based on Beaufort scale colors.
    """
    if wind_speed_ms is None:
        return (213, 208, 205)
    
    # Beaufort scale 12: Hurricane-force (≥ 32.7 m/s)
    if wind_speed_ms >= 32.7:
        return (213, 16, 45)
    
    # Beaufort scale 11: Violent storm (28.5-32.6 m/s)
    elif wind_speed_ms >= 28.5:
        return (237, 41, 18)
    
    # Beaufort scale 10: Storm (24.5-28.4 m/s)
    elif wind_speed_ms >= 24.5:
        return (237, 99, 18)
    
    # Beaufort scale 9: Strong/severe gale (20.8-24.4 m/s)
    elif wind_speed_ms >= 20.8:
        return (237, 143, 18)
    
    # Beaufort scale 8: Gale (17.2-20.7 m/s)
    elif wind_speed_ms >= 17.2:
        return (237, 194, 18)
    
    # Beaufort scale 7: Moderate gale (13.9-17.1 m/s)
    elif wind_speed_ms >= 13.9:
        return (218, 237, 18)
    
    # Beaufort scale 6: Strong breeze (10.8-13.8 m/s)
    elif wind_speed_ms >= 10.8:
        return (164, 237, 18)
    
    # Beaufort scale 5: Fresh breeze (8-10.7 m/s)
    elif wind_speed_ms >= 8.0:
        return (115, 237, 18)
    
    # Beaufort scale 4: Moderate breeze (5.5-7.9 m/s)
    elif wind_speed_ms >= 5.5:
        return (111, 244, 111)
    
    # Beaufort scale 3: Gentle breeze (3.4-5.4 m/s)
    elif wind_speed_ms >= 3.4:
        return (150, 247, 180)
    
    # Beaufort scale 2: Light breeze (1.6-3.3 m/s)
    elif wind_speed_ms >= 1.6:
        return (150, 247, 220)
    
    # Beaufort scale 1: Light air (0.3-1.5 m/s)
    elif wind_speed_ms >= 0.3:
        return (174, 241, 249)
    
    # Beaufort scale 0: Calm (< 0.3 m/s)
    elif wind_speed_ms >= 0:
        return (255, 255, 255)
    
    # Invalid negative values
    else:
        return (213, 208, 205)

def get_color_for_beaufort_scale(beaufort_number):
    """
    Get color for Beaufort scale number based on the official Beaufort scale colors.
    Beaufort number should be 0-12 (or 13-17 for extended scale).
    Returns (r, g, b) tuple based on Beaufort scale colors from Wikipedia.
    """
    if beaufort_number is None or beaufort_number < 0:
        return (213, 208, 205)
    
    # Beaufort scale colors from Wikipedia
    if beaufort_number == 0:
        return (255, 255, 255)
    elif beaufort_number == 1:
        return (174, 241, 249)
    elif beaufort_number == 2:
        return (150, 247, 220)
    elif beaufort_number == 3:
        return (150, 247, 180)
    elif beaufort_number == 4:
        return (111, 244, 111)
    elif beaufort_number == 5:
        return (115, 237, 18)
    elif beaufort_number == 6:
        return (164, 237, 18)
    elif beaufort_number == 7:
        return (218, 237, 18)
    elif beaufort_number == 8:
        return (237, 194, 18)
    elif beaufort_number == 9:
        return (237, 143, 18)
    elif beaufort_number == 10:
        return (237, 99, 18)
    elif beaufort_number == 11:
        return (237, 41, 18)
    elif beaufort_number >= 12:
        return (213, 16, 45)
    else:
        return (213, 208, 205)
