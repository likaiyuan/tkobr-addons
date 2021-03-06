# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    ThinkOpen Solutions Brasil
#    Copyright (C) Thinkopen Solutions <http://www.tkobr.com>.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import logging
import openerp
from openerp.osv import fields, osv, orm
from datetime import date, datetime, time, timedelta
from dateutil.relativedelta import *
from openerp.addons.base.ir.ir_cron import _intervalTypes
from openerp import SUPERUSER_ID
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.http import request
from openerp.tools.translate import _
from openerp import http
import werkzeug.contrib.sessions
from openerp.http import Response

_logger = logging.getLogger(__name__)


# def set_cookie_and_redirect(redirect_url):
#     redirect = werkzeug.utils.redirect(redirect_url, 303)
#     redirect.autocorrect_location_header = False
#     return redirect

    
class Home_tkobr(openerp.addons.web.controllers.main.Home):
    
    def save_session(self, cr, uid, sid, now, context=None):
        session_obj = request.registry.get('ir.sessions')
        user = request.registry.get('res.users').browse(request.cr,
            request.uid, uid, request.context)
        values = {
                  'user_id': uid,
                  'logged_in': True,
                  'session_id': sid,
                  'session_seconds': user.session_default_seconds,
                  'multiple_sessions_block': user.multiple_sessions_block,
                  'date_login': now,
                  'expiration_date': datetime.strftime((datetime.strptime(now, DEFAULT_SERVER_DATETIME_FORMAT) + relativedelta(seconds=user.session_default_seconds)), DEFAULT_SERVER_DATETIME_FORMAT)
                  }
        session = session_obj.search(cr, uid, [('session_id', '=', sid)], context=context)
        session_obj.create(cr, request.uid, values, context=context)
        return True
        
    @http.route('/web/login', type='http', auth="none")
    def web_login(self, redirect=None, **kw):
        openerp.addons.web.controllers.main.ensure_db()
        multi_ok = False
        calendar_set = 0
        calendar_ok = False
        now = fields.datetime.now()
        
        if request.httprequest.method == 'GET' and redirect and request.session.uid:
            return http.redirect_with_hash(redirect)
        
        if not request.uid:
            request.uid = openerp.SUPERUSER_ID
            
        values = request.params.copy()
        if not redirect:
            redirect = '/web?' + request.httprequest.query_string
        values['redirect'] = redirect
        
        try:
            values['databases'] = http.db_list()
        except openerp.exceptions.AccessDenied:
            values['databases'] = None
            
        if request.httprequest.method == 'POST':
            old_uid = request.uid
            uid = False
            if request.params.has_key('login') and request.params.has_key('password'):
                uid = request.session.authenticate(request.session.db,
                    request.params['login'], request.params['password'])
            if uid is not False:
                # check for multiple sessions block
                sessions = request.registry.get('ir.sessions').search(request.cr,
                    request.uid,
                    [('user_id', '=', uid),
                     ('multiple_sessions_block', '=', True),
                     ('logged_in', '=', True)],
                    context=request.context)
                if not sessions:
                    multi_ok = True
                    # check calendars
                    calendar_obj = request.registry.get('resource.calendar')
                    attendance_obj = request.registry.get('resource.calendar.attendance')
                    user = request.registry.get('res.users').browse(request.cr,
                        request.uid, uid, request.context)
                    if user.login_calendar_id:
                        calendar_set += 1
                        # check user calendar
                        attendances = attendance_obj.search(request.cr,
                            request.uid, [('calendar_id', '=', user.login_calendar_id.id),
                                          ('dayofweek', '=', now.weekday()),
                                          ('hour_from', '<=', now.hour),
                                          ('hour_to', '>=', now.hour)],
                            context=request.context)
                        if attendances:
                            calendar_ok = True
                    else:
                        # check user groups calendar
                        for group in user.groups_id:
                            if group.login_calendar_id:
                                calendar_set += 1
                                attendances = attendance_obj.search(request.cr,
                                    request.uid, [('calendar_id', '=', group.login_calendar_id.id),
                                                  ('dayofweek', '=', now.weekday()),
                                                  ('hour_from', '<=', now.hour),
                                                  ('hour_to', '>=', now.hour)],
                                    context=request.context)
                                if attendances:
                                    calendar_ok = True
                                    break
            if (multi_ok == True and ((calendar_set > 0 and calendar_ok == True) or calendar_set == 0)) or uid is SUPERUSER_ID:
                self.save_session(request.cr, uid,
                    request.httprequest.session.sid, now, request.context)
                return http.redirect_with_hash(redirect)
            request.uid = old_uid
            values['error'] = 'Login failed due to one of the following reasons:'
            values['reason1'] = '- Wrong login/password'
            values['reason2'] = '- User not allowed to have multiple logins'
            values['reason3'] = '- User not allowed to login at this specific time and/or day'
        return request.render('web.login', values)
    
    @http.route('/web/session/logout', type='http', auth="none")
    def logout(self, redirect='/web'):
        now = fields.datetime.now()
        if not request.uid:
            request.uid = openerp.SUPERUSER_ID
        sid = request.httprequest.session.sid
        session_obj = request.registry.get('ir.sessions')
        session_id = session_obj.search(request.cr, request.uid,
            [('session_id', '=', sid),
             ('logged_in', '=', True)],
            context=request.context)
        if session_id:
            session = session_obj.read(request.cr, request.uid, session_id[0],
                ['date_login'],
                context=request.context)
            session_obj.write(request.cr, request.uid, session['id'],
                {'logged_in': False,
                 'date_logout': datetime.strptime(now, DEFAULT_SERVER_DATETIME_FORMAT),
                 'logout_type': 'ul',
                 'session_duration': str(datetime.strptime(now, DEFAULT_SERVER_DATETIME_FORMAT) - datetime.strptime(session['date_login'], DEFAULT_SERVER_DATETIME_FORMAT)),
                 },
                context=request.context)
        request.session.logout(keep_db=True)
        return werkzeug.utils.redirect(redirect, 303)
    
    
