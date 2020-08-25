from django.db import models


SYS_OBJECT_TYPE = (
    ('IF', 'SQL インライン テーブル値関数'),
    ('P', 'ストアドプロシージャ'),
    ('V', 'ビュー')
)

class SchemaMaster(models.Model):
    name = models.CharField(max_length=200, unique=True)
    sysobject_type = models.CharField(max_length=10, choices=SYS_OBJECT_TYPE)


class Develop(models.Model):
    master = models.ForeignKey(
        'SchemaMaster', on_delete=models.CASCADE)
    query = models.TextField()
    create_date = models.DateTimeField()


class Staging(models.Model):
    master = models.ForeignKey(
        'SchemaMaster', on_delete=models.CASCADE)
    query = models.TextField()
    create_date = models.DateTimeField()


class Production(models.Model):
    master = models.ForeignKey(
        'SchemaMaster', on_delete=models.CASCADE)
    query = models.TextField()
    create_date = models.DateTimeField()
