def parse_markup(text):
    segments = []
    segment = text[:2]
    bold = False
    for i in range(2, len(text)):
        segment += text[i]
        if text[i - 2:i + 1] == '***':
            segment = segment[:-3]
            if bold:
                package = [segment, 1]
            else:
                package = [segment, 0]
            segments.append(package)
            bold = not bold
            segment = ""
    if segment:
        segments.append([segment, bold])
    return segments
