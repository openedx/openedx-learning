# Generated by Django 4.2.18 on 2025-03-28 02:21

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import openedx_learning.lib.validators


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('oel_publishing', '0005_alter_entitylistrow_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='DraftChangeLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name='UUID')),
                ('changed_at', models.DateTimeField(validators=[openedx_learning.lib.validators.validate_utc_datetime])),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('learning_package', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='oel_publishing.learningpackage')),
            ],
            options={
                'verbose_name': 'Draft Change Log',
                'verbose_name_plural': 'Draft Change Logs',
            },
        ),
        migrations.CreateModel(
            name='DraftChangeLogRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('draft_change_log', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='changes', to='oel_publishing.draftchangelog')),
                ('entity', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, to='oel_publishing.publishableentity')),
                ('new_version', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, to='oel_publishing.publishableentityversion')),
                ('old_version', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, related_name='+', to='oel_publishing.publishableentityversion')),
            ],
            options={
                'verbose_name': 'Draft Log',
                'verbose_name_plural': 'Draft Log',
            },
        ),
        migrations.CreateModel(
            name='DraftSideEffect',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cause', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name='causes', to='oel_publishing.draftchangelogrecord')),
                ('effect', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name='caused_by', to='oel_publishing.draftchangelogrecord')),
            ],
        ),
        migrations.AddConstraint(
            model_name='draftsideeffect',
            constraint=models.UniqueConstraint(fields=('cause', 'effect'), name='oel_pub_dse_uniq_c_e'),
        ),
        migrations.AddIndex(
            model_name='draftchangelogrecord',
            index=models.Index(fields=['entity', '-draft_change_log'], name='oel_dlr_idx_entity_rdcl'),
        ),
        migrations.AddConstraint(
            model_name='draftchangelogrecord',
            constraint=models.UniqueConstraint(fields=('draft_change_log', 'entity'), name='oel_dlr_uniq_dcl'),
        ),
    ]
