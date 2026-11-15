from . import skypilot, lium, vast

# name -> (module, minimum minutes between polls)
REGISTRY = {
    "skypilot": (skypilot, 360),   # AWS/GCP/Azure catalog; refreshes ~daily upstream
    "lium": (lium, 15),
    "vast": (vast, 15),
}
