# -*- coding: utf-8 -*-

from openerp import fields, models


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    def _compute_advance_to_approve(self):
        advance_data = self.env['hr.advance'].read_group([('department_id', 'in', self.ids), ('state', '=', 'submit')], ['department_id'], ['department_id'])
        result = dict((data['department_id'][0], data['department_id_count']) for data in advance_data)
        for department in self:
            department.advance_to_approve_count = result.get(department.id, 0)

    advance_to_approve_count = fields.Integer(compute='_compute_advance_to_approve', string='Advances to Approve')
