# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging
from urllib.parse import urlsplit

import requests

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    logo_fetch_pending = fields.Boolean(
        string='Logo Fetch Pending',
        default=False,
        copy=False,
        help='Whether company logo fetch from Logo.dev is pending.',
    )
    logo_fetch_status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('fetched', 'Fetched'),
            ('not_found', 'Not Found'),
            ('failed', 'Failed'),
        ],
        string='Logo Fetch Status',
        default='pending',
        copy=False,
        help='Result of the latest Logo.dev lookup for this partner.',
    )

    @api.model
    def _extract_domain(self, website=None, email=None):
        """Extract and normalize a domain from website or email."""
        if website and isinstance(website, str) and website.strip():
            raw = website.strip()
            parsed = urlsplit(raw if '://' in raw else f'http://{raw}')
            host = (parsed.hostname or '').strip().lower()
            if host.startswith('www.'):
                host = host[4:]
            if host and '.' in host:
                return host

        if email and isinstance(email, str) and '@' in email:
            domain = email.rsplit('@', 1)[-1].strip().rstrip('>').lower()
            if domain.startswith('www.'):
                domain = domain[4:]
            if domain and '.' in domain:
                return domain

        return None

    @api.model
    def _get_logo_dev_image(self, domain):
        """Fetch company logo from Logo.dev API and return base64 bytes, 'NOT_FOUND', or False."""
        api_key = (
            self.env['ir.config_parameter'].sudo().get_param('logo_dev.api_key') or ''
        ).strip()
        if not api_key or not domain:
            return False

        try:
            response = requests.get(
                f'https://img.logo.dev/{domain}',
                params={
                    'token': api_key,
                    'format': 'png',
                    'size': '200',
                },
                timeout=10,
            )
            if response.status_code == 200 and response.content:
                return base64.b64encode(response.content)
            if response.status_code == 404:
                return 'NOT_FOUND'
            _logger.warning(
                'Logo.dev returned HTTP %s for domain %s',
                response.status_code,
                domain,
            )
        except requests.exceptions.RequestException as exc:
            _logger.warning('Failed to fetch logo from Logo.dev for %s: %s', domain, exc)
        return False

    @api.model_create_multi
    def create(self, vals_list):
        """Optionally fetch company logo on creation or queue for background cron."""
        if self.env.context.get('skip_logo_fetch'):
            return super().create(vals_list)

        params = self.env['ir.config_parameter'].sudo()
        api_key = (params.get_param('logo_dev.api_key') or '').strip()
        immediate_fetch = str(params.get_param('logo_dev.fetch_immediate', 'False')).lower() in ('true', '1')

        for vals in vals_list:
            if vals.get('image_1920'):
                continue
            domain = self._extract_domain(vals.get('website'), vals.get('email'))
            if not domain:
                continue

            if immediate_fetch and api_key:
                logo_data = self._get_logo_dev_image(domain)
                if logo_data and logo_data != 'NOT_FOUND':
                    vals['image_1920'] = logo_data
                    vals['logo_fetch_status'] = 'fetched'
                    vals['logo_fetch_pending'] = False
                elif logo_data == 'NOT_FOUND':
                    vals['logo_fetch_status'] = 'not_found'
                    vals['logo_fetch_pending'] = False
                else:
                    vals['logo_fetch_status'] = 'pending'
                    vals['logo_fetch_pending'] = True
            else:
                vals['logo_fetch_status'] = 'pending'
                vals['logo_fetch_pending'] = True

        return super().create(vals_list)

    def write(self, vals):
        """Optionally fetch company logo when website or email is updated."""
        if self.env.context.get('skip_logo_fetch'):
            return super().write(vals)

        result = super().write(vals)

        if 'website' in vals or 'email' in vals:
            params = self.env['ir.config_parameter'].sudo()
            api_key = (params.get_param('logo_dev.api_key') or '').strip()
            immediate_fetch = str(params.get_param('logo_dev.fetch_immediate', 'False')).lower() in ('true', '1')

            for partner in self:
                if partner.image_1920:
                    continue
                domain = self._extract_domain(partner.website, partner.email)
                if not domain:
                    continue

                if immediate_fetch and api_key:
                    logo_data = self._get_logo_dev_image(domain)
                    if logo_data and logo_data != 'NOT_FOUND':
                        partner.with_context(skip_logo_fetch=True).write({
                            'image_1920': logo_data,
                            'logo_fetch_status': 'fetched',
                            'logo_fetch_pending': False,
                        })
                    elif logo_data == 'NOT_FOUND':
                        partner.with_context(skip_logo_fetch=True).write({
                            'logo_fetch_status': 'not_found',
                            'logo_fetch_pending': False,
                        })
                    else:
                        partner.with_context(skip_logo_fetch=True).write({
                            'logo_fetch_status': 'pending',
                            'logo_fetch_pending': True,
                        })
                else:
                    partner.with_context(skip_logo_fetch=True).write({
                        'logo_fetch_status': 'pending',
                        'logo_fetch_pending': True,
                    })

        return result

    def action_fetch_logo(self):
        """Manually fetch company logos for one or more partners."""
        api_key = (
            self.env['ir.config_parameter'].sudo().get_param('logo_dev.api_key') or ''
        ).strip()
        if not api_key:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Logo.dev API Key Missing'),
                    'message': _('Please configure your Logo.dev API Key in Settings -> General Settings -> Contacts.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }

        fetched_count = 0
        not_found_count = 0
        failed_count = 0
        skipped_count = 0

        for partner in self:
            domain = partner._extract_domain(partner.website, partner.email)
            if not domain:
                skipped_count += 1
                continue

            logo_data = partner._get_logo_dev_image(domain)
            if logo_data and logo_data != 'NOT_FOUND':
                partner.with_context(skip_logo_fetch=True).write({
                    'image_1920': logo_data,
                    'logo_fetch_status': 'fetched',
                    'logo_fetch_pending': False,
                })
                fetched_count += 1
            elif logo_data == 'NOT_FOUND':
                partner.with_context(skip_logo_fetch=True).write({
                    'logo_fetch_status': 'not_found',
                    'logo_fetch_pending': False,
                })
                not_found_count += 1
            else:
                partner.with_context(skip_logo_fetch=True).write({
                    'logo_fetch_status': 'failed',
                    'logo_fetch_pending': False,
                })
                failed_count += 1

        summary_parts = []
        if fetched_count:
            summary_parts.append(_('%d logo(s) fetched') % fetched_count)
        if not_found_count:
            summary_parts.append(_('%d not found') % not_found_count)
        if failed_count:
            summary_parts.append(_('%d failed') % failed_count)
        if skipped_count:
            summary_parts.append(_('%d skipped (no valid domain)') % skipped_count)

        message = ', '.join(summary_parts) if summary_parts else _('No partners processed.')
        notif_type = 'success' if fetched_count and not failed_count else (
            'warning' if failed_count or not_found_count else 'info'
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Logo.dev Enrichment'),
                'message': message,
                'type': notif_type,
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    @api.model
    def _fetch_logo_from_logo_dev(self):
        """Scheduled action (cron) to process queued partner logo lookups in batches."""
        api_key = (
            self.env['ir.config_parameter'].sudo().get_param('logo_dev.api_key') or ''
        ).strip()
        if not api_key:
            return False

        pending_partners = self.search([
            ('logo_fetch_pending', '=', True),
            ('image_1920', '=', False),
        ], limit=50)

        for partner in pending_partners:
            domain = partner._extract_domain(partner.website, partner.email)
            if not domain:
                partner.with_context(skip_logo_fetch=True).write({
                    'logo_fetch_status': 'not_found',
                    'logo_fetch_pending': False,
                })
                continue

            logo_data = partner._get_logo_dev_image(domain)
            if logo_data and logo_data != 'NOT_FOUND':
                partner.with_context(skip_logo_fetch=True).write({
                    'image_1920': logo_data,
                    'logo_fetch_status': 'fetched',
                    'logo_fetch_pending': False,
                })
            elif logo_data == 'NOT_FOUND':
                partner.with_context(skip_logo_fetch=True).write({
                    'logo_fetch_status': 'not_found',
                    'logo_fetch_pending': False,
                })
            else:
                partner.with_context(skip_logo_fetch=True).write({
                    'logo_fetch_status': 'failed',
                    'logo_fetch_pending': False,
                })
        return True