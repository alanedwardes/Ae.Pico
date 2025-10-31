def _rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def get_color_for_temperature(degrees):
    # 41 and higher
    if degrees >= 41:
        return _rgb565(154, 27, 30)  # #9a1b1e
    # 36 to 40
    elif degrees >= 36:
        return _rgb565(193, 32, 38)  # #c12026
    # 30 to 35
    elif degrees >= 30:
        return _rgb565(238, 45, 41)  # #ee2d29
    # 25 to 29
    elif degrees >= 25:
        return _rgb565(235, 80, 56)  # #eb5038
    # 21 to 24
    elif degrees >= 21:
        return _rgb565(242, 106, 48)  # #f26a30
    # 19 to 20
    elif degrees >= 19:
        return _rgb565(246, 138, 31)  # #f68a1f
    # 17 to 18
    elif degrees >= 17:
        return _rgb565(250, 163, 26)  # #faa31a
    # 15 to 16
    elif degrees >= 15:
        return _rgb565(251, 182, 22)  # #fbb616
    # 13 to 14
    elif degrees >= 13:
        return _rgb565(252, 201, 13)  # #fcc90d
    # 11 to 12
    elif degrees >= 11:
        return _rgb565(254, 219, 0)   # #fedb00
    # 9 to 10
    elif degrees >= 9:
        return _rgb565(208, 215, 62)  # #d0d73e
    # 7 to 8
    elif degrees >= 7:
        return _rgb565(175, 210, 81)  # #afd251
    # 5 to 6
    elif degrees >= 5:
        return _rgb565(159, 205, 128) # #9fcd80
    # 3 to 4
    elif degrees >= 3:
        return _rgb565(170, 214, 174) # #aad6ae
    # 1 to 2
    elif degrees >= 1:
        return _rgb565(174, 220, 216) # #aedcd8
    # 0 to -2
    elif degrees >= -2:
        return _rgb565(81, 191, 237)  # #51bfed
    # -3 to -5
    elif degrees >= -5:
        return _rgb565(67, 163, 217)  # #43a3d9
    # -6 to -10
    elif degrees >= -10:
        return _rgb565(55, 137, 198)  # #3789c6
    # -11 to -15
    elif degrees >= -15:
        return _rgb565(35, 116, 182)  # #2374b6
    # -16 to -22
    elif degrees >= -22:
        return _rgb565(2, 98, 169)    # #0262a9
    # -23 and lower
    elif degrees <= -23:
        return _rgb565(31, 71, 153)   # #1f4799
    # Invalid
    else:
        return _rgb565(213, 208, 205) # #d5d0cd

def get_color_for_uv(index):
    if index < 3:
        return _rgb565(113, 180, 102)
    elif index < 6:
        return _rgb565(248, 231, 28)
    elif index < 8:
        return _rgb565(255, 149, 12)
    elif index < 11:
        return _rgb565(215, 41, 33)
    else:
        return _rgb565(102, 0, 224)

def get_color_for_humidity(percentage):
    if percentage <= 20:
        return _rgb565(220, 53, 34)
    elif percentage <= 40:
        return _rgb565(255, 140, 0)
    elif percentage <= 60:
        return _rgb565(76, 175, 80)
    elif percentage <= 80:
        return _rgb565(33, 150, 243)
    elif percentage <= 100:
        return _rgb565(30, 136, 229)
    else:
        return _rgb565(213, 208, 205)

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
        return _rgb565(128, 128, 128)  # Light gray - no rain
    # 1-10% - Very light rain chance
    elif percentage <= 10:
        return _rgb565(150, 150, 150)  # Light gray
    # 11-25% - Light rain chance
    elif percentage <= 25:
        return _rgb565(180, 200, 220)  # Very light blue-gray
    # 26-40% - Moderate rain chance
    elif percentage <= 40:
        return _rgb565(160, 190, 230)  # Light blue-gray
    # 41-60% - High rain chance
    elif percentage <= 60:
        return _rgb565(140, 180, 240)  # Light blue
    # 61-80% - Very high rain chance
    elif percentage <= 80:
        return _rgb565(120, 170, 250)  # Medium light blue
    # 81-95% - Heavy rain chance
    elif percentage <= 95:
        return _rgb565(100, 160, 255)  # Light blue
    # 96-100% - Certain rain
    elif percentage <= 100:
        return _rgb565(80, 150, 255)   # Light blue
    # Invalid values
    else:
        return _rgb565(213, 208, 205)  # Default gray for invalid values

def get_color_for_precip_rate(rate_mmh):
    if rate_mmh is None:
        return _rgb565(213, 208, 205)
    if rate_mmh > 32:
        return _rgb565(179, 0, 0)
    elif rate_mmh >= 16:
        return _rgb565(254, 0, 0)
    elif rate_mmh >= 8:
        return _rgb565(254, 152, 0)
    elif rate_mmh >= 4:
        return _rgb565(254, 203, 0)
    elif rate_mmh >= 2:
        return _rgb565(0, 163, 0)
    elif rate_mmh >= 1:
        return _rgb565(12, 188, 254)
    elif rate_mmh >= 0.5:
        return _rgb565(50, 101, 254)
    elif rate_mmh >= 0:
        return _rgb565(0, 0, 254)
    else:
        return _rgb565(213, 208, 205)

def get_color_for_wind_speed(wind_speed_ms):
    """
    Get color for wind speed based on Beaufort scale.
    Wind speed should be in meters per second (m/s).
    Returns RGB tuple based on Beaufort scale colors.
    """
    if wind_speed_ms is None:
        return _rgb565(213, 208, 205)  # Default gray for invalid values
    
    # Beaufort scale 12: Hurricane-force (≥ 32.7 m/s)
    if wind_speed_ms >= 32.7:
        return _rgb565(213, 16, 45)  # #D5102D - Dark red
    
    # Beaufort scale 11: Violent storm (28.5-32.6 m/s)
    elif wind_speed_ms >= 28.5:
        return _rgb565(237, 41, 18)  # #ED2912 - Red
    
    # Beaufort scale 10: Storm (24.5-28.4 m/s)
    elif wind_speed_ms >= 24.5:
        return _rgb565(237, 99, 18)  # #ED6312 - Red-orange
    
    # Beaufort scale 9: Strong/severe gale (20.8-24.4 m/s)
    elif wind_speed_ms >= 20.8:
        return _rgb565(237, 143, 18)  # #ED8F12 - Orange-red
    
    # Beaufort scale 8: Gale (17.2-20.7 m/s)
    elif wind_speed_ms >= 17.2:
        return _rgb565(237, 194, 18)  # #EDC212 - Orange
    
    # Beaufort scale 7: Moderate gale (13.9-17.1 m/s)
    elif wind_speed_ms >= 13.9:
        return _rgb565(218, 237, 18)  # #DAED12 - Yellow
    
    # Beaufort scale 6: Strong breeze (10.8-13.8 m/s)
    elif wind_speed_ms >= 10.8:
        return _rgb565(164, 237, 18)  # #A4ED12 - Yellow-green
    
    # Beaufort scale 5: Fresh breeze (8-10.7 m/s)
    elif wind_speed_ms >= 8.0:
        return _rgb565(115, 237, 18)  # #73ED12 - Green
    
    # Beaufort scale 4: Moderate breeze (5.5-7.9 m/s)
    elif wind_speed_ms >= 5.5:
        return _rgb565(111, 244, 111)  # #6FF46F - Light green
    
    # Beaufort scale 3: Gentle breeze (3.4-5.4 m/s)
    elif wind_speed_ms >= 3.4:
        return _rgb565(150, 247, 180)  # #96F7B4 - Green
    
    # Beaufort scale 2: Light breeze (1.6-3.3 m/s)
    elif wind_speed_ms >= 1.6:
        return _rgb565(150, 247, 220)  # #96F7DC - Light green
    
    # Beaufort scale 1: Light air (0.3-1.5 m/s)
    elif wind_speed_ms >= 0.3:
        return _rgb565(174, 241, 249)  # #AEF1F9 - Light blue
    
    # Beaufort scale 0: Calm (< 0.3 m/s)
    elif wind_speed_ms >= 0:
        return _rgb565(255, 255, 255)  # #FFFFFF - White
    
    # Invalid negative values
    else:
        return _rgb565(213, 208, 205)  # Default gray for invalid values

def get_color_for_beaufort_scale(beaufort_number):
    """
    Get color for Beaufort scale number based on the official Beaufort scale colors.
    Beaufort number should be 0-12 (or 13-17 for extended scale).
    Returns RGB tuple based on Beaufort scale colors from Wikipedia.
    """
    if beaufort_number is None or beaufort_number < 0:
        return _rgb565(213, 208, 205)  # Default gray for invalid values
    
    # Beaufort scale colors from Wikipedia
    if beaufort_number == 0:
        return _rgb565(255, 255, 255)  # #FFFFFF - White (Calm)
    elif beaufort_number == 1:
        return _rgb565(174, 241, 249)  # #AEF1F9 - Light air
    elif beaufort_number == 2:
        return _rgb565(150, 247, 220)  # #96F7DC - Light breeze
    elif beaufort_number == 3:
        return _rgb565(150, 247, 180)  # #96F7B4 - Gentle breeze
    elif beaufort_number == 4:
        return _rgb565(111, 244, 111)  # #6FF46F - Moderate breeze
    elif beaufort_number == 5:
        return _rgb565(115, 237, 18)   # #73ED12 - Fresh breeze
    elif beaufort_number == 6:
        return _rgb565(164, 237, 18)   # #A4ED12 - Strong breeze
    elif beaufort_number == 7:
        return _rgb565(218, 237, 18)   # #DAED12 - Moderate gale
    elif beaufort_number == 8:
        return _rgb565(237, 194, 18)   # #EDC212 - Gale
    elif beaufort_number == 9:
        return _rgb565(237, 143, 18)   # #ED8F12 - Strong/severe gale
    elif beaufort_number == 10:
        return _rgb565(237, 99, 18)    # #ED6312 - Storm
    elif beaufort_number == 11:
        return _rgb565(237, 41, 18)    # #ED2912 - Violent storm
    elif beaufort_number == 12:
        return _rgb565(213, 16, 45)    # #D5102D - Hurricane-force
    elif beaufort_number >= 13:  # Extended scale (13-17)
        return _rgb565(213, 16, 45)    # #D5102D - Same as hurricane-force for extended scale
    else:
        return _rgb565(213, 208, 205)  # Default gray for invalid values
