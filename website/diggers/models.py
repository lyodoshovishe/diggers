from django.db import models
from django.urls import reverse
from django.contrib.auth.models import AbstractUser
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.conf import settings

import sys
from taggit.managers import TaggableManager
from mptt.models import MPTTModel, TreeForeignKey
from PIL import Image
from io import BytesIO


class User(AbstractUser):
    avatar = models.ImageField(upload_to='uploads/avatars/', blank=True, null=True, verbose_name='Аватар')
    last_activity = models.DateTimeField(null=True, blank=True, verbose_name='Був на сайті')
    email_change_token = models.CharField(max_length=80, verbose_name='Код підтвердження зміни e-mail')
    new_email = models.CharField(max_length=40, null=True, blank=True, verbose_name='Новий e-mail')
    email_verified = models.BooleanField(default=False, verbose_name='e-mail підтверджено')
    is_banned = models.BooleanField(default=False, verbose_name='Заблоковано')

    def get_absolute_url(self):
        return reverse('user', kwargs={'username': self.username})

    def save(self, *args, **kwargs):
        if self.avatar:
            try:
                img = Image.open(self.avatar)
                max_width, max_height = settings.PROFILE_AVATAR_SIZE

                if img.width > max_width or img.height > max_height:
                    output_size = settings.PROFILE_AVATAR_SIZE
                    img.thumbnail(output_size)
                    img = img.convert('RGB')

                    output = BytesIO()
                    img.save(output, format='JPEG')
                    output.seek(0)

                    self.avatar = InMemoryUploadedFile(output, 'ImageField',
                                                       f'{self.avatar.name.split(".")[0]}.jpg',
                                                       'image/jpeg', sys.getsizeof(output),
                                                       None)
            except FileNotFoundError:
                self.avatar = None

        super().save(*args, **kwargs)


class Category(models.Model):
    name = models.CharField(max_length=80, verbose_name='Назва')
    route = models.CharField(max_length=20, verbose_name='Шлях')

    def get_absolute_url(self):
        return '/category/%s/' % self.route

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Категорія'
        verbose_name_plural = 'Категорії'


class Post(models.Model):
    title = models.CharField(max_length=80, verbose_name='Заголовок')
    category = models.ForeignKey(
        Category,
        blank=True,
        null=False,
        verbose_name='Категорія',
        on_delete=models.CASCADE
    )
    text = models.TextField(verbose_name='Текст')
    author = models.ForeignKey(User, verbose_name='Автор', on_delete=models.CASCADE)
    tags = TaggableManager(blank=True, verbose_name='Тэги')
    created_date = models.DateTimeField(auto_now_add=True, verbose_name='Дата створення')
    modified_date = models.DateTimeField(auto_now=True, verbose_name='Дата редагування')
    is_hidden = models.BooleanField(default=False, verbose_name='Зробити прихованим')

    def _tags(self):
        return [t.name for t in self.tags.all()]

    def get_absolute_url(self):
        return reverse('post_detail', kwargs={'pk': self.pk})

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Пост'
        verbose_name_plural = 'Пости'
        permissions = (
            ('moderate_post', 'Модерація постів'),
            ('hidden_access', 'Доступ до прихованих постів'),
        )


class Comment(MPTTModel):
    post = models.ForeignKey(Post, verbose_name='Пост', on_delete=models.CASCADE)
    author = models.ForeignKey(User, verbose_name='Автор', on_delete=models.CASCADE)
    text = models.TextField(verbose_name='Текст')
    parent = TreeForeignKey(
        'self',
        null=True,
        blank=True,
        related_name='children',
        db_index=True,
        verbose_name='Відповідь на',
        on_delete=models.CASCADE
    )
    is_deleted = models.BooleanField(default=False, verbose_name='Видалено')
    created_date = models.DateTimeField(auto_now_add=True, verbose_name='Дата створення')
    modified_date = models.DateTimeField(auto_now=True, verbose_name='Дата редагування')

    def __str__(self):
        return self.text[:80]

    class Meta:
        verbose_name = 'Коментар'
        verbose_name_plural = 'Коментарі'
        permissions = (
            ('moderate_comment', 'Модерація коментарів'),
        )

    class MPTTMeta:
        order_insertion_by = ['created_date']


class Map(models.Model):
    title = models.CharField(max_length=80, verbose_name='Назва')
    file = models.ImageField(upload_to='uploads/%Y/%m/%d/', verbose_name='Файл')
    description = models.TextField(blank=True, verbose_name='Опис')
    author = models.ForeignKey(User, verbose_name='Автор', on_delete=models.CASCADE)
    tags = TaggableManager(blank=True, verbose_name='Тэги')
    created_date = models.DateTimeField(auto_now_add=True, verbose_name='Дата створення')
    modified_date = models.DateTimeField(auto_now=True, verbose_name='Дата редагування')

    def _tags(self):
        return [t.name for t in self.tags.all()]

    def get_absolute_url(self):
        return reverse('map', kwargs={'pk': self.pk})

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Мапа'
        verbose_name_plural = 'Мапи'
        permissions = (
            ('moderate_map', 'Модерація мап'),
            ('map_access', 'Доступ до мап'),
        )
