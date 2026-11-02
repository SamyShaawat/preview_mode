{
    'name': 'Preview Mode',
    'summary': 'See what a button click will do before it does it',
    'version': '20.0.1.0.0',
    'category': 'Productivity',
    'author': 'Samy Mostafa Shaawat',
    'license': 'OPL-1',
    'depends': ['base', 'web'],
    'assets': {
        'web.assets_backend': [
            'preview_mode/static/src/**/*',
        ],
    },
    'post_load': 'post_load',
    'installable': True,
    'application': False,
}
