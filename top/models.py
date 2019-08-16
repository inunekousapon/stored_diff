from django.db import models


class StoredProcedureMaster(models.Model):
    name = models.CharField(max_length=200, unique=True)


class Develop(models.Model):
    master = models.ForeignKey(
        'StoredProcedureMaster', on_delete=models.CASCADE)
    query = models.TextField()
    create_date = models.DateTimeField()


class Staging(models.Model):
    master = models.ForeignKey(
        'StoredProcedureMaster', on_delete=models.CASCADE)
    query = models.TextField()
    create_date = models.DateTimeField()


class Production(models.Model):
    master = models.ForeignKey(
        'StoredProcedureMaster', on_delete=models.CASCADE)
    query = models.TextField()
    create_date = models.DateTimeField()
