# -*- coding: utf-8 -*-
# Part of auth_otp_login. See LICENSE file for full copyright and licensing details.

import json
from datetime import timedelta

from odoo import http, fields
from odoo.exceptions import AccessError
from odoo.http import request


class AuthOtpDashboard(http.Controller):
    """Admin-only security dashboard for the Email OTP Login module.

    Deliberately built as a fully self-contained, hand-crafted HTML page
    (its own CSS animations, hand-built SVG charts, vanilla JS) rather
    than a standard Odoo list/kanban/pivot view - the goal here is a
    genuinely custom, high-impact visual, which Odoo's own view types
    are not designed to provide. No external CDN or library dependency:
    everything renders and animates using only what ships in the page
    itself, so it works identically offline and can never break due to
    a third-party host being unreachable.
    """

    def _check_access(self):
        if not request.env.user.has_group('base.group_system'):
            raise AccessError('You do not have access to the OTP Security Dashboard.')

    @http.route('/otp/dashboard', type='http', auth='user', website=False, sitemap=False)
    def dashboard(self, **kw):
        self._check_access()
        return request.render('auth_otp_login.otp_dashboard_template', {})

    @http.route('/otp/dashboard/data', type='http', auth='user', methods=['GET'],
                website=False, sitemap=False)
    def dashboard_data(self, **kw):
        self._check_access()
        data = self._compute_stats()
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')],
        )

    def _compute_stats(self):
        Otp = request.env['res.users.otp'].sudo()
        UnregLog = request.env['auth.otp.unregistered.login'].sudo()
        RestrictedLog = request.env['auth.otp.restricted.login'].sudo()

        now = fields.Datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total_generated = Otp.search_count([])
        total_verified = Otp.search_count([('state', '=', 'verified')])
        # A code that was requested but never used keeps the "pending" state
        # until the daily cleanup runs. Judge by its expiry time instead, so
        # the numbers are right at every moment, not only after the cleanup.
        total_pending = Otp.search_count([
            ('state', '=', 'pending'), ('expiration_date', '>=', now),
        ])
        total_expired = Otp.search_count([
            '|', ('state', '=', 'expired'),
            '&', ('state', '=', 'pending'), ('expiration_date', '<', now),
        ])
        today_verified = Otp.search_count([
            ('state', '=', 'verified'), ('create_date', '>=', today_start),
        ])
        active_users = len(Otp.search([('state', '=', 'verified')]).mapped('user_id'))
        unregistered_probes = UnregLog.search_count([])
        blocked_attempts = RestrictedLog.search_count([])
        success_rate = round((total_verified / total_generated * 100), 1) if total_generated else 0.0

        # 14-day trend of successful logins
        trend = []
        for i in range(13, -1, -1):
            day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            count = Otp.search_count([
                ('state', '=', 'verified'),
                ('create_date', '>=', day_start),
                ('create_date', '<', day_end),
            ])
            trend.append({'label': day_start.strftime('%b %d'), 'value': count})

        # Top users by successful OTP logins
        verified_recs = Otp.search([('state', '=', 'verified')])
        counts_by_user = {}
        for rec in verified_recs:
            counts_by_user[rec.user_id] = counts_by_user.get(rec.user_id, 0) + 1
        top_users = sorted(counts_by_user.items(), key=lambda kv: kv[1], reverse=True)[:5]
        top_users_data = [{'name': user.name or user.login, 'count': count} for user, count in top_users]

        # Merged recent activity feed across all three tracking models
        feed = []
        for rec in Otp.search([], order='create_date desc', limit=15):
            abandoned = rec.state == 'pending' and rec.expiration_date < now
            feed.append({
                'kind': 'expired' if abandoned else rec.state,  # pending / verified / expired
                'label': rec.login or (rec.user_id.login or ''),
                'time': fields.Datetime.to_string(rec.create_date),
            })
        for rec in UnregLog.search([], order='create_date desc', limit=15):
            feed.append(
                {'kind': 'unregistered', 'label': rec.login, 'time': fields.Datetime.to_string(rec.create_date)})
        for rec in RestrictedLog.search([], order='create_date desc', limit=15):
            feed.append({'kind': 'restricted', 'label': rec.login, 'time': fields.Datetime.to_string(rec.create_date)})
        feed.sort(key=lambda e: e['time'], reverse=True)
        feed = feed[:15]

        return {
            'stats': {
                'total_verified': total_verified,
                'today_verified': today_verified,
                'success_rate': success_rate,
                'active_users': active_users,
                'unregistered_probes': unregistered_probes,
                'blocked_attempts': blocked_attempts,
            },
            'breakdown': {
                'verified': total_verified,
                'expired': total_expired,
                'pending': total_pending,
            },
            'trend': trend,
            'top_users': top_users_data,
            'feed': feed,
            'generated_at': fields.Datetime.to_string(now),
        }
