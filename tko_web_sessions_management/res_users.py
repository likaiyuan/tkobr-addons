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
from openerp import SUPERUSER_ID
from openerp.http import request
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)

class res_users(osv.osv):
    _inherit = 'res.users'
    
    _columns = { 
        'session_id' : fields.char('Session ID', size=100),
        'expiration_date' : fields.datetime('Expiration Date'),
        'logged_in': fields.boolean('Logged in'),
        'multiple_sessions': fields.boolean('Multiple Sessions'),
        }
    
    def _login(self, db, login, password):
        cr = self.pool.cursor()
        cr.autocommit(True)
        user_id = super(res_users, self)._login(db, login, password)
        
        try:
            session_id = request.httprequest.session.sid
            temp_browse = self.browse(cr, SUPERUSER_ID, user_id)
            if isinstance(temp_browse, list): temp_browse = temp_browse[0]
            exp_date = temp_browse.expiration_date
            if exp_date and temp_browse.session_id:
                exp_date = datetime.strptime(exp_date, "%Y-%m-%d %H:%M:%S")
                if exp_date < datetime.utcnow() or temp_browse.session_id != session_id:
                    raise openerp.exceptions.AccessDenied()
            self.save_session(cr, user_id)
        except openerp.exceptions.AccessDenied:
            user_id = False
            _logger.warn("User %s is already logged in into the system!", login)
            _logger.warn("Multiple sessions are not allowed for security reasons!")
        finally:
            cr.close()
    
        return user_id

    # clears session_id and session expiry from res.users
    def clear_session(self, cr, user_id):
        if isinstance(user_id, list): user_id = user_id[0]
        self.write(cr, SUPERUSER_ID, user_id, {'session_id':'', 'expiration_date':False, 'logged_in':False})

    # insert session_id and session expiry into res.users
    def save_session(self, cr, user_id):
        if isinstance(user_id, list): user_id = user_id[0]
        exp_date = datetime.utcnow() + timedelta(minutes=2)
        sid = request.httprequest.session.sid
        self.write(cr, SUPERUSER_ID, user_id, {'session_id':sid, 'expiration_date':exp_date, 'logged_in':True})

    # schedular function to validate users session
    def validate_sessions(self, cr, uid):
        ids = self.search(cr, SUPERUSER_ID, [('expiration_date', '!=', False)])
        users = self.browse(cr, SUPERUSER_ID, ids)
        
        for user_id in users:
            exp_date = datetime.strptime(user_id.expiration_date, "%Y-%m-%d %H:%M:%S")
            if exp_date < datetime.utcnow():
                self.clear_session(cr, user_id.id)
