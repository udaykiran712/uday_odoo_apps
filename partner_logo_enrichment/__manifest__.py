# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Partner Logo Enrichment (Logo.dev)',
    'version': '18.0.1.0.0',
    'category': 'Contacts',
    'summary': 'Automatically fetch and enrich partner company logos from Logo.dev API using website or email domain.',
    'description': """
Partner Logo Enrichment (Logo.dev)
==================================
Automatically enriches partner records (res.partner) with high-resolution
company logos using the Logo.dev API.

Key Features:
- Smart Domain Extraction from Partner Website or Email address
- 1-Click "Test Connection" button in General Settings to verify Logo.dev API Key
- Dual Execution Modes: Immediate Fetch on Save or 15-Minute Background Cron Queue
- One-Click "Fetch Logo" Smart Button on the Partner Form view
- Multi-Record "Fetch Partner Logos" Bulk Server Action in Contacts List/Form views
- Smart HTTP 404 Not Found handling to prevent infinite cron retry loops
    """,
    'author': 'Gardas Udaykiran',
    'website': 'https://www.linkedin.com/in/udaykirangardas/',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'base_setup',
    ],
    'data': [
        'data/ir_cron_data.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
    ],
    'images': [
        'static/description/banner.gif',
        'static/description/enrichment_preview.gif',
        'static/description/how_it_works.gif',
        'static/description/reliability_banner.gif',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}