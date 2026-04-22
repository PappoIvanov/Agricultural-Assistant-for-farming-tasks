from pyproj import Transformer

_transformer = Transformer.from_crs("EPSG:7801", "EPSG:4326", always_xy=True)

def _bgs_to_wgs84(x, y):
    lon, lat = _transformer.transform(x, y)
    return lat, lon

_p1_lat, _p1_lon = _bgs_to_wgs84(290935.183, 4704924.557)

PARCELS = {
    "Парцел 1": {
        "lat": _p1_lat,
        "lon": _p1_lon,
        "area_dka": 10,
    },
    "Парцел 2": {
        # TODO: добави координатите на Парцел 2
        "lat": None,
        "lon": None,
        "area_dka": None,
    },
}

# TODO: потвърди точните стойности на място
ROSE_CONFIG = {
    "row_spacing_m": 2.0,
    "canopy_width_m": 0.5,
    "nozzles": {
        "green": {
            "model": "Lechler TR 80-015",
            "flow_l_min_at_2bar": 0.46,
            "use": "зима и начало на пролетта",
        },
        "yellow": {
            "model": "Lechler TR 80-02",
            "flow_l_min_at_2bar": 0.62,
            "use": "край на пролетта, развито растение",
        },
    },
    # TODO: потвърди скоростта на трактора
    "tractor_speed_kmh": None,
}

DIARY_PATH = "01_Дневник_Операции/ШАБЛОН_дневник.md"
AGRO_DIARY_PATH = "01_Дневник_Операции/Агротехнически_Дневник.md"
BABH_DIARY_PATH = "01_Дневник_Операции/2026/Дневник+за+проведени+РЗ+мероприятия+и+торене.docx"
LITERATURE_PATHS = [
    "01_Дневник_Операции/Литература/",
    "03_Препарати_и_Торове/Литература/",
]
