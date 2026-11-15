from . import skypilot, lium, vast, nebius, aws_live, prime, gcp_preempt

# name -> (module, minimum minutes between polls)
REGISTRY = {
    "skypilot": (skypilot, 360),   # AWS/GCP/Azure catalog; refreshes ~daily upstream
    "nebius": (nebius, 15),
    "aws_live": (aws_live, 60),
    "prime": (prime, 30),
    "gcp_preempt": (gcp_preempt, 360),
    "lium": (lium, 15),
    "vast": (vast, 15),
}
