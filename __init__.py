from . import models, controllers


def post_load():
    from .models.guards import install_patches
    install_patches()
