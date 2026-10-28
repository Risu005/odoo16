# -*- coding: utf-8 -*-

from datetime import date

from odoo import fields, models, _
from odoo.exceptions import UserError


class ProjectBusinessUnitReportWizard(models.TransientModel):
    _name = 'project.business.unit.report.wizard'
    _description = 'Project Business Unit Report Wizard'

    business_unit_tag_id = fields.Many2one(
        'project.tags',
        string='Business Unit',
        required=True,
        help='Only projects carrying this tag will appear in the PDF.',
    )

    def action_print_report(self):
        self.ensure_one()

        if not self.business_unit_tag_id:
            raise UserError(_('Please select a business unit.'))

        return self.env.ref(
            'project_report.action_business_unit_project_report'
        ).report_action(self)

    def get_report_lines(self):
        self.ensure_one()

        report_date = fields.Date.context_today(self)

        projects = self.env['project.project'].search(
            [
                ('tag_ids', 'in', self.business_unit_tag_id.ids),
            ],
            order='date_start asc, id asc',
        )

        # Only projects that are still open.
        projects = projects.filtered(
            lambda project: not self._is_project_completed(project)
        )

        lines = [
            self._prepare_project_line(project, report_date)
            for project in projects
        ]

        # Drop projects that have no open action points left.
        # Comment out the next three lines to keep those rows in the PDF
        # showing "No pending action points".
        lines = [
            line for line in lines
            if line['pending_tasks']
        ]

        return lines

    def _prepare_project_line(self, project, report_date):
        start_date = self._to_date(project.date_start)
        close_date = self._to_date(project.date)

        days_taken = ''

        if start_date:
            days_taken = max(
                (report_date - start_date).days,
                0,
            )

        days_left = ''

        if close_date:
            days_left = max(
                (close_date - report_date).days,
                0,
            )

        pending_tasks = self.env['project.task'].search(
            self._get_open_task_domain(project),
            order='date_deadline asc, sequence asc, id asc',
        )

        return {
            'project_type': self._get_project_type(project),
            'project_id': self._get_project_reference(project),
            'customer_name': project.partner_id.display_name or '',
            'project_name': project.name or '',
            'business_unit': self.business_unit_tag_id.name or '',
            'start_date': start_date,
            'close_date': close_date,
            'days_taken': days_taken,
            'days_left': days_left,
            'pending_tasks': pending_tasks,
        }

    def _get_open_task_domain(self, project):
        """Build the domain for tasks that are still outstanding.

        A task counts as completed when any of the following is true:

        - its kanban state is green, which is how this database marks a
          task as done and matches the Monthly Task Report;
        - it sits in a folded stage;
        - its custom Task Status is Completed or Cancelled.
        """
        task_fields = self.env['project.task']._fields

        domain = [
            ('project_id', '=', project.id),
            ('kanban_state', '!=', 'done'),
            ('stage_id.fold', '=', False),
        ]

        # Custom Task Status field defined in models/project_task.py.
        if 'status' in task_fields:
            domain.append(
                ('status', 'not in', ['completed', 'cancelled'])
            )

        return domain

    @staticmethod
    def _to_date(value):
        if not value:
            return False

        if isinstance(value, date):
            return value

        return fields.Date.to_date(value)

    @staticmethod
    def _is_project_completed(project):
        if 'status' in project._fields and project.status in (
            'completed', 'cancelled'
        ):
            return True

        stage = (
            project.stage_id
            if 'stage_id' in project._fields
            else False
        )

        if not stage:
            return False

        stage_name = (stage.name or '').lower()

        return bool(
            stage.fold
            or 'complete' in stage_name
            or 'closed' in stage_name
            or 'cancel' in stage_name
        )

    @staticmethod
    def _get_project_type(project):
        # First check for an explicit custom project-type field.
        for field_name in ('project_type', 'type'):
            field = project._fields.get(field_name)

            if not field:
                continue

            value = project[field_name]

            if not value:
                continue

            if field.type == 'selection':
                selection = dict(
                    field._description_selection(project.env)
                )
                return selection.get(value, value)

            if field.type == 'many2one':
                return value.display_name

            return str(value)

        # Otherwise derive Internal/External from project stage.
        stage = (
            project.stage_id
            if 'stage_id' in project._fields
            else False
        )

        stage_name = stage.name if stage else ''
        lowered_stage_name = stage_name.lower()

        if 'external' in lowered_stage_name:
            return 'External'

        if 'internal' in lowered_stage_name:
            return 'Internal'

        return stage_name or 'Not Specified'

    def _get_project_reference(self, project):
        # Use the custom reference or code field when available.
        for field_name in ('reference', 'code'):
            if (
                field_name in project._fields
                and project[field_name]
            ):
                return project[field_name]

        # Otherwise find a PRJ tag, excluding the selected BU tag.
        other_tags = (
            project.tag_ids
            - self.business_unit_tag_id
        )

        reference_tag = other_tags.filtered(
            lambda tag: (
                tag.name or ''
            ).upper().startswith(
                ('PRJ-', 'PROJECT-')
            )
        )[:1]

        return (
            reference_tag.name
            if reference_tag
            else ''
        )