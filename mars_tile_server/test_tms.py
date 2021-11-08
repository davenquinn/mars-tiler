from morecantile import tms

mercator_tms = tms.get("WebMercatorQuad")

pos_0 = (149.936, -3.752, 13)


def test_web_mercator_quad():
    tile = mercator_tms.tile(*pos_0)
    assert tile.z == pos_0[2]
    assert tile.x == 7507
    assert tile.y == 4181
