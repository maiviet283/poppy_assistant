from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Offering',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True, verbose_name='Name')),
                ('price', models.DecimalField(decimal_places=2, max_digits=9, verbose_name='Price')),
                ('duration_minutes', models.PositiveIntegerField(default=30, verbose_name='Duration (minutes)')),
                ('description', models.CharField(blank=True, max_length=255, verbose_name='Description')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
            ],
            options={
                'verbose_name': 'Offering',
                'verbose_name_plural': 'Offerings',
                'db_table': 'poppy_offering',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Resource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True, verbose_name='Name')),
                ('type_label', models.CharField(blank=True, max_length=60, verbose_name='Type')),
                ('specialty', models.CharField(blank=True, max_length=255, verbose_name='Specialty')),
                ('capacity', models.PositiveIntegerField(default=1, verbose_name='Capacity')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
            ],
            options={
                'verbose_name': 'Resource',
                'verbose_name_plural': 'Resources',
                'db_table': 'poppy_resource',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Booking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('customer_name', models.CharField(max_length=120, verbose_name='Customer name')),
                ('phone', models.CharField(blank=True, max_length=40, verbose_name='Phone')),
                ('offering', models.CharField(blank=True, max_length=120, verbose_name='Offering')),
                ('resource', models.CharField(blank=True, max_length=120, verbose_name='Requested resource')),
                ('appointment_time_text', models.CharField(blank=True, max_length=120, verbose_name='Appointment time (as said)')),
                ('start_time', models.DateTimeField(blank=True, null=True, verbose_name='Start time')),
                ('notes', models.TextField(blank=True, verbose_name='Notes')),
                ('source', models.CharField(choices=[('chat', 'Chat'), ('voice', 'Voice')], default='chat', max_length=10)),
                ('status', models.CharField(choices=[('new', 'New'), ('confirmed', 'Confirmed'), ('done', 'Done'), ('cancelled', 'Cancelled')], default='new', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Booking',
                'verbose_name_plural': 'Bookings',
                'db_table': 'poppy_booking',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['phone'], name='poppy_booki_phone_ce4ead_idx'), models.Index(fields=['start_time'], name='poppy_booki_start_t_e63a3f_idx')],
            },
        ),
    ]
