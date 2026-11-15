from . import skypilot, lium, vast, nebius, aws_live, prime

# name -> (module, minimum minutes between polls)
REGISTRY = {
    "skypilot": (skypilot, 360),   # AWS/GCP/Azure catalog; refreshes ~daily upstream
    "nebius": (nebius, 15),
    "aws_live": (aws_live, 60),
    "prime": (prime, 30),
    "lium": (lium, 15),
    "vast": (vast, 15),
}
