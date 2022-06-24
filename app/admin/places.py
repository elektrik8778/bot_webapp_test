import os
import json
from app import db, Config
from app.admin import bp
from app.models import Place, Placement
from app.admin.forms import PlaceForm, PlacementForm
from flask import render_template, request, redirect
from werkzeug.utils import secure_filename
import openpyxl
from openpyxl.cell import Cell
from openpyxl import styles


@bp.get('/admin/places')
def places_view():
    places = Place.query.all()
    return render_template('admin/places.html', places=places)


@bp.post('/admin/place/<pid>')
@bp.get('/admin/place/<pid>')
def place_view(pid):
    place = Place.query.get(int(pid))
    placements = Placement.query.filter(Placement.place == int(pid)).all()
    place_form = PlaceForm()
    placement_form = PlacementForm()

    if request.method == 'POST':
        if place_form.validate_on_submit() and place_form.save.data:
            pid = int(request.form.get('pid'))
            if pid == 0:
                place = Place()
                db.session.add(place)
            else:
                place: Place = Place.query.get(int(pid))

            place.name = place_form.name.data
            place.description = place_form.description.data
            db.session.commit()
            return redirect(f'/admin/place/{place.id}')

        elif placement_form.validate_on_submit() and placement_form.save_placement.data:
            uploaded_file = placement_form.excel_file.data
            filename = secure_filename(uploaded_file.filename)
            placement = Placement()
            placement.place = place.id
            placement.name = placement_form.name.data
            placement.excel_filename = filename
            db.session.add(placement)
            db.session.commit()
            placement_catalog = os.path.join(os.path.join(Config.UPLOAD_FOLDER, 'placements', str(placement.id)))
            if not os.path.exists(placement_catalog):
                os.makedirs(placement_catalog)
            uploaded_file.save(os.path.join(placement_catalog, filename))
            placement.placement = create_placement(placement_catalog, filename)
            db.session.commit()
            return redirect(request.referrer)

    return render_template('admin/place.html',
                           place=place,
                           place_form=place_form,
                           placements=placements,
                           placement_form=placement_form)


@bp.get('/admin/show_placement/<pmid>')
def show_placement(pmid):
    placement: Placement = Placement.query.get(int(pmid))
    title = f'Зал {placement.get_place().name}, рассадка {placement.name}'
    return render_template('admin/show_placement.html',
                           title=title,
                           placement=placement)


from colorsys import rgb_to_hls, hls_to_rgb
# From: https://stackoverflow.com/questions/58429823/getting-excel-cell-background-themed-color-as-hex-with-openpyxl/58443509#58443509
#   which refers to: https://pastebin.com/B2nGEGX2 (October 2020)
#       Updated to use list(elem) instead of the deprecated elem.getchildren() method
#       which has now been removed completely from Python 3.9 onwards.
#https://bitbucket.org/openpyxl/openpyxl/issues/987/add-utility-functions-for-colors-to-help
RGBMAX = 0xff  # Corresponds to 255
HLSMAX = 240  # MS excel's tint function expects that HLS is base 240. see:
# https://social.msdn.microsoft.com/Forums/en-US/e9d8c136-6d62-4098-9b1b-dac786149f43/excel-color-tint-algorithm-incorrect?forum=os_binaryfile#d3c2ac95-52e0-476b-86f1-e2a697f24969


def rgb_to_ms_hls(red, green=None, blue=None):
    """Converts rgb values in range (0,1) or a hex string of the form '[#aa]rrggbb' to HLSMAX based HLS, (alpha values are ignored)"""
    if green is None:
        if isinstance(red, str):
            if len(red) > 6:
                red = red[-6:]  # Ignore preceding '#' and alpha values
            blue = int(red[4:], 16) / RGBMAX
            green = int(red[2:4], 16) / RGBMAX
            red = int(red[0:2], 16) / RGBMAX
        else:
            red, green, blue = red
    h, l, s = rgb_to_hls(red, green, blue)
    return (int(round(h * HLSMAX)), int(round(l * HLSMAX)), int(round(s * HLSMAX)))


def ms_hls_to_rgb(hue, lightness=None, saturation=None):
    """Converts HLSMAX based HLS values to rgb values in the range (0,1)"""
    if lightness is None:
        hue, lightness, saturation = hue
    return hls_to_rgb(hue / HLSMAX, lightness / HLSMAX, saturation / HLSMAX)


def rgb_to_hex(red, green=None, blue=None):
    """Converts (0,1) based RGB values to a hex string 'rrggbb'"""
    if green is None:
        red, green, blue = red
    return ('%02x%02x%02x' % (int(round(red * RGBMAX)), int(round(green * RGBMAX)), int(round(blue * RGBMAX)))).upper()


def get_theme_colors(wb):
    """Gets theme colors from the workbook"""
    # see: https://groups.google.com/forum/#!topic/openpyxl-users/I0k3TfqNLrc
    from openpyxl.xml.functions import QName, fromstring
    xlmns = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    root = fromstring(wb.loaded_theme)
    themeEl = root.find(QName(xlmns, 'themeElements').text)
    colorSchemes = themeEl.findall(QName(xlmns, 'clrScheme').text)
    firstColorScheme = colorSchemes[0]

    colors = []

    for c in ['lt1', 'dk1', 'lt2', 'dk2', 'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6']:
        accent = firstColorScheme.find(QName(xlmns, c).text)
        for i in list(accent): # walk all child nodes, rather than assuming [0]
            if 'window' in i.attrib['val']:
                colors.append(i.attrib['lastClr'])
            else:
                colors.append(i.attrib['val'])

    return colors


def tint_luminance(tint, lum):
    """Tints a HLSMAX based luminance"""
    # See: http://ciintelligence.blogspot.co.uk/2012/02/converting-excel-theme-color-and-tint.html
    if tint < 0:
        return int(round(lum * (1.0 + tint)))
    else:
        return int(round(lum * (1.0 - tint) + (HLSMAX - HLSMAX * (1.0 - tint))))


def theme_and_tint_to_rgb(wb, theme, tint):
    """Given a workbook, a theme number and a tint return a hex based rgb"""
    rgb = get_theme_colors(wb)[theme]
    h, l, s = rgb_to_ms_hls(rgb)
    return rgb_to_hex(ms_hls_to_rgb(h, tint_luminance(tint, l), s))


def create_placement(path, filename):
    wb = openpyxl.load_workbook(filename=os.path.join(path, filename))
    sheet_places = wb['вариант 1']
    schemeData = []
    for r in sheet_places:

        for c in r:
            print(r,c)
            if c.value:
                # print(c.value, c.coordinate)
                theme = c.fill.start_color.theme
                tint = c.fill.start_color.tint
                color = "3300CC"
                price = 0
                if type(theme) == int:
                    color = theme_and_tint_to_rgb(wb, theme, tint)
                    sheet_prices = wb['цены']
                    for row in sheet_prices:
                        for cell in row:
                            theme = cell.fill.start_color.theme
                            tint = cell.fill.start_color.tint
                            price_color = theme_and_tint_to_rgb(wb, theme, tint)
                            if color == price_color:
                                price = cell.value
                if c.value.split('\n')[0] == 'надпись':

                    schemeData.append({
                        "NomBilKn": "1338",
                        "ObjectName": "Label",
                        "ObjectType": "Label",
                        "Width": "680",
                        "Height": "60",
                        "CX": f"{c.col_idx*100}",
                        "CX2": f"{c.col_idx*100 + 50}",
                        "CY": f"{c.row*100 + 25}",
                        "CY2": f"{c.row*100 + 45}",
                        "Angle": "0.00",
                        "Row": f"",
                        "Seat": "",
                        "cod_sec": "0",
                        "Name_sec": str(c.value.split('\n')[-1]),
                        "FreeOfferSeat": "0",
                        "FontColor": "000000",
                        "FontSize": "10",
                        "Label": "11",
                        "MinX": "119",
                        "MinY": "128",
                        "MaxX": "8491",
                        "MaxY": "6771",
                        "BackColor": color,
                        "avail": True,
                        "name_sec": str(c.value.split('\n')[-1]),
                        "Price": price,
                        "PriceSell": f"{price}.0000"
                    })
                elif c.value.split('\n')[0] in ['место', 'пусто']:
                    schemeData.append({
                        "NomBilKn": "1338",
                        "ObjectName": "Place",
                        "ObjectType": "Place",
                        "Width": "64",
                        "Height": "64",
                        "CX": f"{c.col_idx * 100}",
                        "CX2": f"{c.col_idx * 100 + 50}",
                        "CY": f"{c.row * 100}",
                        "CY2": f"{c.row * 100 + 20}",
                        "Angle": "0.00",
                        "Row": str(c.value.split('\n')[1].split('ряд')[1].strip()),
                        "Seat": str(c.value.split('\n')[2].split('место')[1].strip()),
                        "cod_sec": "2",
                        "Name_sec": str(c.value.split('\n')[3]),
                        "FreeOfferSeat": "0",
                        "FontColor": "",
                        "FontSize": "0",
                        "Label": "0",
                        "MinX": "119",
                        "MinY": "128",
                        "MaxX": "8491",
                        "MaxY": "6771",
                        "BackColor": color,
                        "avail": True if c.value.split('\n')[0] == 'место' else False,
                        "name_sec": str(c.value.split('\n')[3]),
                        "Price": price,
                        "PriceSell": f"{price}.0000"
                    })
    wb.close()
    with open(os.path.join(path, f'{filename.split(".")[0]}.js'), 'w') as jsdata:
        jsdata.write(f'var schemeData = {json.dumps(schemeData)}')

    return schemeData
