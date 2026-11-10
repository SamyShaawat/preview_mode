{
    'name': 'Preview Mode',
    'summary': 'Shows what a button click will create, change or delete, and where, before you confirm it',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'author': 'Samy Mostafa Shaawat',
    'website': 'https://github.com/SamyShaawat/preview_mode',
    'maintainer': 'Samy Mostafa Shaawat',
    'maintainers': ['SamyShaawat'],
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    # PORT: Odoo 16 to 19 ACL file is security/ir.model.access.csv (Odoo 20 uses ir.access.csv).
    'data': ['security/ir.model.access.csv', 'security/preview_mode_security.xml'],
    'assets': {
        'web.assets_backend': [
            'preview_mode/static/src/**/*',
        ],
        'web.assets_tests': [
            'preview_mode/static/tests/tours/**/*',
        ],
    },
    # The Store shows the first image as the banner and the one ending in
    # _screenshot as the large screenshot.
    'images': [
        'static/description/banner.png',
        'static/description/main_screenshot.png',
        'static/description/popup-create.png',
        'static/description/popup-journal.png',
        'static/description/popup-archive.png',
        'static/description/popup-fails.png',
        'static/description/popup-arabic.png',
        'static/description/toast-created.png',
    ],
    'post_load': 'post_load',
    'installable': True,
    # A background tool, not an app of its own: no menu, no entry in the Apps filter "Applications".
    'application': False,
}
