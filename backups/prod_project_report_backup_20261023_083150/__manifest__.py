# -*- coding: utf-8 -*-

{
    'name': 'Project Report',
    'version': '16.0.1.1.0',
    'summary': 'Generate project and task reports to share with customers',
    'description': """
Project reporting module for generating task, project update,
weekly, monthly, implementation plan, and business-unit reports.
    """,
    'author': 'Mtwa Mgimwa',
    'category': 'Services/Project',
    'license': 'LGPL-3',

    'depends': [
        'project',
        'mail',
    ],

    'data': [
        # Security
        'security/ir.model.access.csv',

        # Email templates
        'data/email_templates.xml',

        # Report actions and templates
        'report/task_reports.xml',
        'report/project_update.xml',
        'report/project_weekly_report.xml',
        'report/project_monthly_report.xml',
        'report/project_impl_plan_report.xml',
        'report/business_unit_project_report.xml',

        # Views and report wizards
        'views/task_report_views.xml',
        'views/business_unit_report_wizard_views.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}