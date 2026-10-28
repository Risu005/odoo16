# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import base64


class ProjectTask(models.Model):
    _inherit = 'project.task'

    report_start_date = fields.Date(
        string='Start Date',
        help='Explicit start date to be used in project reports instead of task creation date.'
    )

    date_last_report = fields.Date(
        string='Last Report Date',
        help='Date when the last report was generated for this task'
    )
    project_milestone = fields.Char(
        string='Project Milestone',
        help='Current milestone of the project'
    )
    additional_comment = fields.Text(
        string='Additional Comments',
        help='Additional comments for the daily report'
    )
    action_required_from_customer = fields.Text(
        string='Action Required from Customer',
        help='Actions that need to be taken by the customer'
    )

    status = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('testing', 'Testing'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
        ('cancelled', 'Cancelled'),
    ], string='Task Status', default='not_started', help='Current status of the task')

    def action_generate_daily_report(self):
        """Generate daily report from task data"""
        self.ensure_one()
        self.date_last_report = fields.Date.today()
        return self.env.ref('project_report.task_report_pdf').report_action(self)

    def action_send_task_report_email(self):
        """Send task daily report via email"""
        self.ensure_one()

        if not self.project_id:
            raise UserError(_("No project found for this task"))
        if not self.project_id.partner_id:
            raise UserError(_("No customer found for project %s") % self.project_id.name)
        if not self.project_id.partner_id.email:
            raise UserError(_("No customer email found for project %s") % self.project_id.name)

        self.date_last_report = fields.Date.today()

        template = self.env.ref('project_report.email_template_task_report')

        ctx = dict(self.env.context)
        ctx.update({
            'default_template_id': template.id,
            'default_res_id': self.id,
            'default_model': 'project.task',
            'default_use_template': True,
            'default_composition_mode': 'comment',
            'default_report_date': fields.Date.today(),
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Task Report'),
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'target': 'new',
            'context': ctx,
        }

    def action_print_task_report(self):
        """Print task report"""
        self.ensure_one()
        self.date_last_report = fields.Date.today()
        return self.env.ref('project_report.task_report_pdf').report_action(self)

    @api.model
    def get_customer_contact_person(self):
        """Get the primary contact person from the customer"""
        try:
            if not self.project_id or not self.project_id.partner_id:
                return 'Not specified'

            contact_person = self.project_id.partner_id.child_ids.filtered(
                lambda c: not c.is_company and c.function
            )
            if contact_person:
                return f"{contact_person[0].name} ({contact_person[0].function})"

            return self.project_id.partner_id.name
        except Exception:
            return 'Not specified'

    @api.model
    def get_project_id_code(self):
        """Get project ID code - use project reference or generate from sequence"""
        try:
            if not self.project_id:
                return 'No Project'

            if self.project_id.tag_ids:
                return self.project_id.tag_ids[0].name

            if hasattr(self.project_id, 'code') and self.project_id.code:
                return self.project_id.code
            elif hasattr(self.project_id, 'reference') and self.project_id.reference:
                return self.project_id.reference
            else:
                return f"P{self.project_id.id:05d}-{datetime.now().year}"
        except Exception:
            return 'Not Available'

    @api.model
    def get_current_milestone(self):
        """Get current milestone from milestone_id field"""
        try:
            if hasattr(self, 'milestone_id') and self.milestone_id:
                return self.milestone_id.name

            if self.project_milestone:
                return self.project_milestone

            if not self.stage_id:
                return 'Not specified'

            stage_name = self.stage_id.name.lower()
            if 'new' in stage_name or 'draft' in stage_name:
                return 'Planning & Requirements'
            elif 'progress' in stage_name or 'doing' in stage_name:
                return 'Implementation & Development'
            elif 'test' in stage_name or 'review' in stage_name:
                return 'Testing & Quality Assurance'
            elif 'wait' in stage_name:
                return 'Waiting for Customer Input'
            elif 'done' in stage_name or self.stage_id.fold:
                return 'Completion & Handover'
            else:
                return self.stage_id.name
        except Exception:
            return 'Not specified'

    @api.model
    def get_project_dates(self):
        """Get project start and end dates"""
        try:
            if not self.project_id:
                return ('Not set', 'Not set')

            project = self.project_id

            start_date = 'Not set'
            end_date = 'Not set'

            if project.date_start:
                start_date = project.date_start.strftime('%d %B %Y')

            if project.date:
                end_date = project.date.strftime('%d %B %Y')
            elif self.date_deadline:
                end_date = self.date_deadline.strftime('%d %B %Y')

            return (start_date, end_date)
        except Exception:
            return ('Not set', 'Not set')

    @api.model
    def get_task_done_today(self):
        """Get work done today"""
        try:
            if self.description:
                return self.description

            if not self.stage_id:
                return f"Task: {self.name or 'Unnamed Task'}"

            stage_actions = {
                'new': f"Task created: {self.name}",
                'progress': f"Working on: {self.name}",
                'done': f"Completed: {self.name}",
                'test': f"Testing: {self.name}",
                'wait': f"Awaiting feedback for: {self.name}",
            }

            stage_name = self.stage_id.name.lower()
            for key, action in stage_actions.items():
                if key in stage_name:
                    return action

            return f"{self.name} - {self.stage_id.name}"
        except Exception:
            return 'Task information not available'

    @api.model
    def get_next_actions(self):
        """Get next action items from task description"""
        try:
            if self.description:
                return self.description.strip()
            else:
                return ''
        except Exception:
            return ''

    @api.model
    def get_customer_actions_required(self):
        """Get actions required from customer"""
        try:
            if self.action_required_from_customer:
                return self.action_required_from_customer

            if not self.stage_id:
                return "No specific action required at this time"

            stage_name = self.stage_id.name.lower()
            if 'wait' in stage_name:
                return "Customer feedback/approval required to proceed"
            elif 'test' in stage_name or 'review' in stage_name:
                return "Customer testing and sign-off required"
            elif self.stage_id.fold:
                return "Final acceptance and project closure"
            elif 'new' in stage_name:
                return "Project kick-off meeting and site access coordination"
            else:
                return "No specific action required at this time"
        except Exception:
            return "No specific action required at this time"

    @api.model
    def get_subtask_summary(self):
        """Get summary of subtasks with their status"""
        try:
            if not self.child_ids:
                return []

            subtasks = []
            for subtask in self.child_ids:
                subtasks.append({
                    'name': subtask.name or 'Unnamed Subtask',
                    'assignee': ', '.join(subtask.user_ids.mapped('name')) if subtask.user_ids else 'Unassigned',
                    'stage': subtask.stage_id.name if subtask.stage_id else 'No Stage',
                    'is_done': subtask.stage_id.fold if subtask.stage_id else False,
                    'priority': dict(subtask._fields['priority'].selection).get(subtask.priority, 'Normal') if hasattr(subtask, 'priority') else 'Normal',
                })
            return subtasks
        except Exception:
            return []

    @api.model
    def get_all_task_assignees(self):
        """Get all assignees from main task and subtasks"""
        try:
            all_assignees = set()

            if self.user_ids:
                all_assignees.update(self.user_ids.mapped('name'))

            if self.child_ids:
                for subtask in self.child_ids:
                    if subtask.user_ids:
                        all_assignees.update(subtask.user_ids.mapped('name'))

            if all_assignees:
                return ', '.join(sorted(all_assignees))
            else:
                return 'Not assigned'
        except Exception:
            return 'Not assigned'


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('report_start_date'):
                vals['report_start_date'] = fields.Date.today()
        return super().create(vals_list)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    reference = fields.Char(
        string='Project Reference',
        help='External project reference number'
    )
    milestone = fields.Char(
        string='Current Milestone',
        help='Current project milestone'
    )

    def action_generate_project_report(self):
        """Generate project report from project data"""
        self.ensure_one()
        return self.env.ref('project_report.project_report_pdf').report_action(self)

    def action_send_project_report_email(self):
        """Send project daily report via email"""
        self.ensure_one()

        if not self.partner_id:
            raise UserError(_("No customer found for project %s") % self.name)
        if not self.partner_id.email:
            raise UserError(_("No customer email found for project %s") % self.name)

        template = self.env.ref('project_report.email_template_project_daily_report')

        ctx = dict(self.env.context)
        ctx.update({
            'default_template_id': template.id,
            'default_res_id': self.id,
            'default_model': 'project.project',
            'default_use_template': True,
            'default_composition_mode': 'comment',
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Project Report'),
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'target': 'new',
            'context': ctx,
        }