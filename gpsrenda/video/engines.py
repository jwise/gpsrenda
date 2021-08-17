from gpsrenda.globals import globals

ENGINE_PREFERENCE = [ 'gstreamer', 'moviepy' ]

engines = {}

def register_engine(engine, name = None):
    if name is None:
        name = engine.__name__
    engines[name] = engine

def _get_default_engine():
    if globals['video']['engine'] is not None:
        # User forced a video engine.
        engine = engines.get(globals['video']['engine'], None)
        if engine is None:
            raise ModuleNotFoundError(f"video engine \"{globals['video']['engine']}\" is not available")
    
    # Ok, try the defaults, in order of preference.
    for name in ENGINE_PREFERENCE:
        if name in engines:
            return engines[name]
    
    # None of those?  Well, grab anything we can find.
    if len(engines) == 0:
        raise ModuleNotFoundError("no video engines available")
    return list(engines.items())[0][1]

def default_engine(renderfn):
    return _get_default_engine()(renderfn)
