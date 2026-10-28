# -*- coding: utf-8 -*-

import calendar
from datetime import date, datetime, time, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectMonthlyReportWizard(models.TransientModel):
    _name = 'project.monthly.report.wizard'
    _description = 'Project Registration and Completion Report Wizard'

    PERIOD_SELECTION = [
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    MONTH_SELECTION = [
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ]

    CATEGORY_SELECTION = [
        ('registered', 'Projects Registered'),
        ('completed', 'Projects Completed'),
        ('both', 'Both'),
    ]

    report_period = fields.Selection(
        selection=PERIOD_SELECTION,
        string='Reporting Period',
        required=True,
        default='monthly',
        help='Select Weekly or Monthly reporting frequency.',
    )

    # Weekly selection fields (Monday to Sunday by default)
    reference_date = fields.Date(
        string='Week Selector Date',
        default=fields.Date.context_today,
        help='Select any date within the desired week to automatically calculate Monday (start) and Sunday (end).',
    )
    week_start_date = fields.Date(
        string='Week Start Date',
        default=lambda self: self._default_week_start_date(),
        help='Start date of the reporting week (Monday by default, inclusive).',
    )
    week_end_date = fields.Date(
        string='Week End Date',
        default=lambda self: self._default_week_end_date(),
        help='End date of the reporting week (Sunday by default, inclusive).',
    )

    # Monthly selection fields
    month = fields.Selection(
        selection=MONTH_SELECTION,
        string='Reporting Month',
        required=True,
        default=lambda self: str(fields.Date.context_today(self).month),
        help='Select the month for which to generate the project report.',
    )
    year = fields.Integer(
        string='Reporting Year',
        required=True,
        default=lambda self: fields.Date.context_today(self).year,
        help='Select the year for which to generate the project report.',
    )

    report_category = fields.Selection(
        selection=CATEGORY_SELECTION,
        string='Report Category',
        required=True,
        default='both',
        help='Choose whether to include registered projects, completed projects, or both.',
    )

    @staticmethod
    def _get_week_bounds(target_date):
        """Return (monday, sunday) for the calendar week containing `target_date`.

        Follows the existing Weekly Task Report convention where Monday is the start
        of the week (`weekday() == 0`) and Sunday is the end (`monday + 6 days`).
        """
        ref = fields.Date.to_date(target_date)
        monday = ref - timedelta(days=ref.weekday())
        sunday = monday + timedelta(days=6)
        return monday, sunday

    @api.model
    def _default_week_start_date(self):
        today = fields.Date.context_today(self)
        monday, _sunday = self._get_week_bounds(today)
        return monday

    @api.model
    def _default_week_end_date(self):
        today = fields.Date.context_today(self)
        _monday, sunday = self._get_week_bounds(today)
        return sunday

    @api.onchange('reference_date')
    def _onchange_reference_date(self):
        if self.reference_date:
            monday, sunday = self._get_week_bounds(self.reference_date)
            self.week_start_date = monday
            self.week_end_date = sunday

    @api.onchange('week_start_date')
    def _onchange_week_start_date(self):
        if self.week_start_date and (
            not self.week_end_date or self.week_end_date < self.week_start_date
        ):
            self.week_end_date = self.week_start_date + timedelta(days=6)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Automatically infer weekly mode when weekly date parameters are passed without report_period
            if 'report_period' not in vals and any(
                k in vals for k in ('week_start_date', 'week_end_date', 'reference_date')
            ) and 'month' not in vals:
                vals['report_period'] = 'weekly'

            if vals.get('report_period') == 'weekly':
                if vals.get('reference_date') and not vals.get('week_start_date') and not vals.get('week_end_date'):
                    monday, sunday = self._get_week_bounds(vals['reference_date'])
                    vals['week_start_date'] = monday
                    vals['week_end_date'] = sunday
                elif vals.get('week_start_date') and not vals.get('week_end_date'):
                    start_dt = fields.Date.to_date(vals['week_start_date'])
                    vals['week_end_date'] = start_dt + timedelta(days=6)
                elif vals.get('week_end_date') and not vals.get('week_start_date'):
                    end_dt = fields.Date.to_date(vals['week_end_date'])
                    vals['week_start_date'] = end_dt - timedelta(days=6)

        return super().create(vals_list)

    @api.constrains('report_period', 'month', 'year', 'week_start_date', 'week_end_date')
    def _check_period_parameters(self):
        for wizard in self:
            if wizard.report_period == 'weekly':
                if not wizard.week_start_date or not wizard.week_end_date:
                    raise UserError(_('Please select both a Week Start Date and a Week End Date.'))
                if wizard.week_start_date > wizard.week_end_date:
                    raise UserError(_('Week Start Date cannot be later than Week End Date.'))
            else:
                if not wizard.month or int(wizard.month) not in range(1, 13):
                    raise UserError(_('Please select a valid reporting month (January to December).'))
                if not wizard.year or wizard.year < 1900 or wizard.year > 9999:
                    raise UserError(_('Please enter a valid 4-digit reporting year.'))

    def _check_month_and_year(self):
        """Backward-compatible validation helper for monthly parameters."""
        for wizard in self:
            if not wizard.month or int(wizard.month) not in range(1, 13):
                raise UserError(_('Please select a valid reporting month (January to December).'))
            if not wizard.year or wizard.year < 1900 or wizard.year > 9999:
                raise UserError(_('Please enter a valid 4-digit reporting year.'))

    def action_print_report(self):
        """Validate selections and trigger the downloadable Weekly or Monthly Project Report PDF."""
        self.ensure_one()
        self._check_period_parameters()
        if self.report_period == 'weekly':
            return self.env.ref(
                'project_report.action_project_weekly_report_pdf'
            ).report_action(self)
        return self.env.ref(
            'project_report.action_project_monthly_report_pdf'
        ).report_action(self)

    def get_week_date_range(self):
        """Return (start_date, end_date, start_datetime, end_datetime_exclusive) for the selected week.

        - `start_date`: inclusive start date (Monday by default)
        - `end_date`: inclusive end date (Sunday by default)
        - `start_datetime`: inclusive lower bound (`start_date 00:00:00`)
        - `end_datetime_exclusive`: exclusive upper bound (`(end_date + 1 day) 00:00:00`)
        """
        self.ensure_one()
        if not self.week_start_date or not self.week_end_date:
            raise UserError(_('Please select both a Week Start Date and a Week End Date.'))
        if self.week_start_date > self.week_end_date:
            raise UserError(_('Week Start Date cannot be later than Week End Date.'))

        start_date = self._to_date(self.week_start_date)
        end_date = self._to_date(self.week_end_date)
        start_datetime = datetime.combine(start_date, time.min)
        end_datetime_exclusive = datetime.combine(end_date + timedelta(days=1), time.min)

        return start_date, end_date, start_datetime, end_datetime_exclusive

    def get_month_date_range(self):
        """Return (start_date, end_date, start_datetime, end_datetime_exclusive) for the selected month and year.

        Handles 28/29/30/31-day months (including leap years) with an inclusive start
        (`YYYY-MM-01 00:00:00`) and exclusive end (`next_month_day_1 00:00:00`).
        """
        self.ensure_one()
        self._check_month_and_year()

        month_int = int(self.month)
        year_int = int(self.year)
        last_day = calendar.monthrange(year_int, month_int)[1]

        start_date = date(year_int, month_int, 1)
        end_date = date(year_int, month_int, last_day)
        start_datetime = datetime.combine(start_date, time.min)
        end_datetime_exclusive = datetime.combine(end_date + timedelta(days=1), time.min)

        return start_date, end_date, start_datetime, end_datetime_exclusive

    def get_period_date_range(self):
        """Return (start_date, end_date, start_datetime, end_datetime_exclusive) for the active report_period."""
        self.ensure_one()
        if self.report_period == 'weekly':
            return self.get_week_date_range()
        return self.get_month_date_range()

    def get_report_frequency_label(self):
        """Return 'Weekly' or 'Monthly'."""
        self.ensure_one()
        return dict(self.PERIOD_SELECTION).get(self.report_period, 'Monthly')

    def get_month_name(self):
        """Return the display name of the selected reporting month."""
        self.ensure_one()
        return dict(self.MONTH_SELECTION).get(str(self.month), '')

    def get_period_label(self):
        """Return formatted label for the selected reporting period."""
        self.ensure_one()
        if self.report_period == 'weekly':
            start_date, end_date, _s_dt, _e_dt = self.get_week_date_range()
            return f"{start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')}"
        return f"{self.get_month_name()} {self.year}".strip()

    def get_report_title(self):
        """Return the main heading for the report."""
        self.ensure_one()
        if self.report_period == 'weekly':
            return f"Weekly Project Report ({self.get_period_label()})"
        return f"Monthly Project Report ({self.get_period_label()})"

    def get_report_category_label(self):
        """Return the display label of the selected report category."""
        self.ensure_one()
        return dict(self.CATEGORY_SELECTION).get(self.report_category, '')

    def include_registered_section(self):
        """Return True if the Registered Projects section should be shown."""
        self.ensure_one()
        return self.report_category in ('registered', 'both')

    def include_completed_section(self):
        """Return True if the Completed Projects section should be shown."""
        self.ensure_one()
        return self.report_category in ('completed', 'both')

    def get_registered_projects(self):
        """Return recordset of projects registered (created) within the selected period,
        regardless of their current status.

        Uses inclusive start (`create_date >= start_datetime`) and exclusive end
        (`create_date < end_datetime_exclusive`) so time components on boundary dates
        never exclude matching projects.
        """
        self.ensure_one()
        _start_date, _end_date, start_datetime, end_datetime_exclusive = self.get_period_date_range()

        projects = self.env['project.project'].search(
            [
                ('create_date', '>=', start_datetime),
                ('create_date', '<', end_datetime_exclusive),
            ],
            order='create_date asc, id asc',
        )

        # Deduplicate while preserving chronological order
        seen_ids = set()
        unique_ids = []
        for project in projects:
            if project.id not in seen_ids:
                seen_ids.add(project.id)
                unique_ids.append(project.id)

        return self.env['project.project'].browse(unique_ids)

    def get_registered_project_lines(self):
        """Prepare tabular report lines for projects registered in the selected period."""
        self.ensure_one()
        projects = self.get_registered_projects()
        return [
            self._prepare_project_line(project)
            for project in projects
        ]

    def get_completed_projects(self):
        """Return recordset of projects completed within the selected period,
        regardless of when they were registered or started.

        Uses inclusive start (`completion_dt >= start_datetime`) and exclusive end
        (`completion_dt < end_datetime_exclusive`) on the actual completion timestamp.
        """
        self.ensure_one()
        _start_date, _end_date, start_datetime, end_datetime_exclusive = self.get_period_date_range()

        all_projects = self.env['project.project'].search([], order='id asc')

        seen_ids = set()
        matched = []
        for project in all_projects:
            if project.id in seen_ids:
                continue
            if not self._is_project_completed(project):
                continue

            completion_dt = self._get_project_completion_datetime(project)
            if completion_dt and start_datetime <= completion_dt < end_datetime_exclusive:
                seen_ids.add(project.id)
                matched.append((completion_dt, project.id))

        matched.sort(key=lambda item: (item[0], item[1]))
        return self.env['project.project'].browse([item[1] for item in matched])

    def get_completed_project_lines(self):
        """Prepare tabular report lines for projects completed in the selected period."""
        self.ensure_one()
        _start_date, _end_date, start_datetime, end_datetime_exclusive = self.get_period_date_range()

        all_projects = self.env['project.project'].search([], order='id asc')

        seen_ids = set()
        matched_lines = []
        for project in all_projects:
            if project.id in seen_ids:
                continue
            if not self._is_project_completed(project):
                continue

            completion_dt = self._get_project_completion_datetime(project)
            if completion_dt and start_datetime <= completion_dt < end_datetime_exclusive:
                seen_ids.add(project.id)
                matched_lines.append(
                    self._prepare_project_line(
                        project,
                        completion_date=self._to_date(completion_dt),
                        completion_datetime=completion_dt,
                    )
                )

        matched_lines.sort(
            key=lambda line: (
                line.get('completion_datetime') or datetime.min,
                line['record_id'],
            )
        )
        return matched_lines

    def _prepare_project_line(self, project, completion_date=None, completion_datetime=None):
        """Build a dictionary of project fields for rendering in the QWeb report tables."""
        if completion_datetime is None and self._is_project_completed(project):
            completion_datetime = self._get_project_completion_datetime(project)
        if completion_date is None and completion_datetime:
            completion_date = self._to_date(completion_datetime)

        return {
            'record_id': project.id,
            'project': project,
            'project_id': self._get_project_reference(project),
            'project_name': project.name or '',
            'customer_name': project.partner_id.display_name if project.partner_id else 'Not specified',
            'manager_name': project.user_id.name if project.user_id else 'Not assigned',
            'start_date': self._to_date(project.date_start),
            'planned_end_date': self._to_date(project.date),
            'registration_date': self._to_date(project.create_date),
            'registration_datetime': project.create_date or False,
            'completion_date': completion_date or False,
            'completion_datetime': completion_datetime or False,
            'status': self._get_project_status_display(project),
        }

    @staticmethod
    def _to_date(value):
        """Safely convert a Date, Datetime, or string value to a python date object."""
        if not value:
            return False
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return fields.Date.to_date(value)

    @staticmethod
    def _to_datetime(value):
        """Safely convert a Datetime, Date, or string value to a python datetime object."""
        if not value:
            return False
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, time(12, 0, 0))
        return fields.Datetime.to_datetime(value)

    @classmethod
    def _is_stage_completed(cls, stage):
        """Return True if a project.project.stage record represents a completed state."""
        if not stage:
            return False
        stage_name = (stage.name or '').lower()
        if 'cancel' in stage_name:
            return False
        if any(keyword in stage_name for keyword in ('complete', 'done', 'closed')):
            return True
        if stage.fold and 'other' not in stage_name:
            return True
        return False

    @classmethod
    def _is_project_completed(cls, project):
        """Determine whether a project is currently in a completed state."""
        if hasattr(project, '_is_completed_state'):
            return project._is_completed_state()

        if 'status' in project._fields:
            if project.status == 'cancelled':
                return False
            if project.status == 'completed':
                return True

        stage = project.stage_id if 'stage_id' in project._fields else False
        stage_name = (stage.name or '').lower() if stage else ''

        if 'cancel' in stage_name:
            return False

        if cls._is_stage_completed(stage):
            return True

        if 'last_update_status' in project._fields and project.last_update_status == 'on_track':
            last_update = (
                project.last_update_id
                if 'last_update_id' in project._fields
                else False
            )
            if last_update and last_update.status == 'on_track':
                return True

        return False

    def _get_project_completion_datetime(self, project):
        """Return the actual completion `datetime` of a completed project.

        Resolution order:
        1. Explicit completion timestamp (`project.completed_date` or other dedicated
           completion date field on `project.project`), recorded automatically when the
           project transitions to a completed state.
        2. Recorded transition into a completed stage in `mail.tracking.value` or
           recorded `'Completed'` (`status == 'on_track'`) `project.update`.
        3. If the project was created directly in a completed stage with no subsequent
           stage transition, its `create_date`.

        Note: Never substitutes `project.date` (planned end date) or `project.write_date`
        (last modification date) for the actual completion date.
        """
        if not self._is_project_completed(project):
            return False

        # 1. Check explicit completion timestamp field (`completed_date` etc.)
        for field_name in (
            'completed_date',
            'completion_date',
            'date_completed',
            'date_closed',
        ):
            if field_name in project._fields and project[field_name]:
                return self._to_datetime(project[field_name])

        # 2. Delegate to the model's historical completion transition resolver
        if hasattr(project, '_resolve_historical_completion_datetime'):
            resolved = project._resolve_historical_completion_datetime()
            if resolved:
                return self._to_datetime(resolved)

        return False

    def _get_project_completion_date(self, project):
        """Return the actual completion `date` of a completed project."""
        completion_dt = self._get_project_completion_datetime(project)
        return self._to_date(completion_dt) if completion_dt else False

    @classmethod
    def _get_project_status_display(cls, project):
        """Return a human-readable current status for the project."""
        if 'status' in project._fields and project.status:
            selection = dict(project._fields['status']._description_selection(project.env))
            return selection.get(project.status, project.status)

        stage = project.stage_id if 'stage_id' in project._fields else False
        stage_name = stage.name if stage else ''

        if cls._is_project_completed(project):
            if stage_name and any(
                word in stage_name.lower() for word in ('complete', 'done', 'closed')
            ):
                return stage_name
            return 'Completed'

        if stage_name:
            return stage_name

        if 'last_update_status' in project._fields and project.last_update_status:
            selection = dict(
                project._fields['last_update_status']._description_selection(project.env)
            )
            return selection.get(project.last_update_status, project.last_update_status)

        return 'In Progress'

    @staticmethod
    def _get_project_reference(project):
        """Return the project reference/code following the module's existing conventions."""
        for field_name in ('reference', 'code'):
            if field_name in project._fields and project[field_name]:
                return project[field_name]

        if 'tag_ids' in project._fields and project.tag_ids:
            reference_tag = project.tag_ids.filtered(
                lambda tag: (tag.name or '').upper().startswith(('PRJ-', 'PROJECT-'))
            )[:1]
            if reference_tag:
                return reference_tag.name
            return project.tag_ids[0].name or ''

        year = (project.create_date or datetime.now()).year
        return f"P{project.id:05d}-{year}"
