def get_color_for_temperature(degrees):
    # 41 and higher
    if degrees >= 41:
        return (154, 27, 30)  # #9a1b1e
    # 36 to 40
    elif degrees >= 36:
        return (193, 32, 38)  # #c12026
    # 30 to 35
    elif degrees >= 30:
        return (238, 45, 41)  # #ee2d29
    # 25 to 29
    elif degrees >= 25:
        return (235, 80, 56)  # #eb5038
    # 21 to 24
    elif degrees >= 21:
        return (242, 106, 48)  # #f26a30
    # 19 to 20
    elif degrees >= 19:
        return (246, 138, 31)  # #f68a1f
    # 17 to 18
    elif degrees >= 17:
        return (250, 163, 26)  # #faa31a
    # 15 to 16
    elif degrees >= 15:
        return (251, 182, 22)  # #fbb616
    # 13 to 14
    elif degrees >= 13:
        return (252, 201, 13)  # #fcc90d
    # 11 to 12
    elif degrees >= 11:
        return (254, 219, 0)   # #fedb00
    # 9 to 10
    elif degrees >= 9:
        return (208, 215, 62)  # #d0d73e
    # 7 to 8
    elif degrees >= 7:
        return (175, 210, 81)  # #afd251
    # 5 to 6
    elif degrees >= 5:
        return (159, 205, 128) # #9fcd80
    # 3 to 4
    elif degrees >= 3:
        return (170, 214, 174) # #aad6ae
    # 1 to 2
    elif degrees >= 1:
        return (174, 220, 216) # #aedcd8
    # 0 to -2
    elif degrees >= -2:
        return (81, 191, 237)  # #51bfed
    # -3 to -5
    elif degrees >= -5:
        return (67, 163, 217)  # #43a3d9
    # -6 to -10
    elif degrees >= -10:
        return (55, 137, 198)  # #3789c6
    # -11 to -15
    elif degrees >= -15:
        return (35, 116, 182)  # #2374b6
    # -16 to -22
    elif degrees >= -22:
        return (2, 98, 169)    # #0262a9
    # -23 and lower
    elif degrees <= -23:
        return (31, 71, 153)   # #1f4799
    # Invalid
    else:
        return (213, 208, 205) # #d5d0cd

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
    if percentage <= 30:
        return (220, 53, 34)  # Very Dry - red
    elif percentage <= 50:
        return (255, 140, 0)  # Dry - orange
    elif percentage <= 70:
        return (76, 175, 80)  # Comfortable - green
    elif percentage <= 85:
        return (33, 150, 243)  # Humid - light blue
    elif percentage <= 100:
        return (30, 136, 229)  # Very Humid - dark blue
    else:
        return (213, 208, 205)  # Default gray for invalid values

def get_color_for_rain_percentage(percentage):
    # 0% - No rain
    if percentage == 0:
        return (128, 128, 128)  # Light gray - no rain
    # 1-10% - Very light rain chance
    elif percentage <= 10:
        return (150, 150, 150)  # Light gray
    # 11-25% - Light rain chance
    elif percentage <= 25:
        return (180, 200, 220)  # Very light blue-gray
    # 26-40% - Moderate rain chance
    elif percentage <= 40:
        return (160, 190, 230)  # Light blue-gray
    # 41-60% - High rain chance
    elif percentage <= 60:
        return (140, 180, 240)  # Light blue
    # 61-80% - Very high rain chance
    elif percentage <= 80:
        return (120, 170, 250)  # Medium light blue
    # 81-95% - Heavy rain chance
    elif percentage <= 95:
        return (100, 160, 255)  # Light blue
    # 96-100% - Certain rain
    elif percentage <= 100:
        return (80, 150, 255)   # Light blue
    # Invalid values
    else:
        return (213, 208, 205)  # Default gray for invalid values