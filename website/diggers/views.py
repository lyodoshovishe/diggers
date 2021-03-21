from django.views import generic
from django.views.generic.detail import SingleObjectMixin
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.conf import settings
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from next_prev import next_in_order, prev_in_order

from django.contrib.auth.views import LoginView
from django_registration.backends.activation.views import ActivationView, RegistrationView as ActivationEmailMixin
from django_registration.backends.one_step.views import RegistrationView as OneStepRegistrationView
from django_registration.exceptions import ActivationError
from django.template.loader import render_to_string

from .models import Category, User, Post
from .forms import PostForm, ExtendedLoginForm


# Create your views here.


class PostList(generic.ListView):
    paginate_by = settings.POSTS_PER_PAGE
    context_object_name = 'posts'

    def get_queryset(self):
        query = {}

        if 'category' in self.kwargs:
            query['category'] = get_object_or_404(Category, route=self.kwargs['category'])

        if 'tags' in self.kwargs:
            query['tags__name__in'] = self.kwargs['tags'].split(",")

        if not self.request.user.has_perm('diggers.hidden_access'):
            query['is_hidden'] = False

        q = {k: v for k, v in query.items() if v is not None}

        return Post.objects.filter(Q(**q)).distinct().order_by('-created_date', '-pk')


class PostListByAuthor(SingleObjectMixin, generic.ListView):
    paginate_by = settings.POSTS_PER_PAGE
    slug_field = 'username'
    query_pk_and_slug = True

    def __init__(self):
        self.object = None

    def get(self, request, *args, **kwargs):
        self.object = self.get_object(queryset=User.objects.all())
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['author'] = self.object
        ctx['posts'] = self.object_list
        return ctx

    def get_queryset(self):
        not_hidden = not self.request.user.has_perm('diggers.hidden_access')
        author = self.object.pk
        return Post.objects.filter(author__pk=author, is_hidden=not_hidden).distinct().order_by('-created_date', '-pk')


class PostDetail(generic.DetailView):
    model = Post

    def get_context_data(self, **kwargs):
        ctx = super(PostDetail, self).get_context_data(**kwargs)

        query = {}
        if not self.request.user.has_perm('diggers.hidden_access'):
            query['is_hidden'] = False

        qs = Post.objects.all().order_by('created_date', 'pk')
        current = ctx['post']
        ctx['next_post'] = next_in_order(current, qs=qs)
        ctx['prev_post'] = prev_in_order(current, qs=qs)
        return ctx


class PostCreate(LoginRequiredMixin, UserPassesTestMixin, generic.CreateView):
    model = Post
    form_class = PostForm
    template_name_suffix = '_create_form'

    def test_func(self):
        return self.request.user.email_verified is True

    def get_initial(self):
        self.initial.update({'author': self.request.user})
        return self.initial


class PostUpdate(LoginRequiredMixin, generic.UpdateView):
    model = Post
    form_class = PostForm
    template_name_suffix = '_update_form'

    def get_initial(self):
        self.initial.update({'author': self.request.user})
        return self.initial


class PostDelete(LoginRequiredMixin, generic.DeleteView):
    model = Post
    template_name_suffix = '_confirm_delete'
    success_url = reverse_lazy('diggers:post_list')


class ExtendedLoginView(LoginView):
    form_class = ExtendedLoginForm

    def form_valid(self, form):
        remember_me = form.cleaned_data['remember_me']
        if not remember_me:
            self.request.session.set_expiry(0)
            self.request.session.modified = True
        return super(ExtendedLoginView, self).form_valid(form)


class ExtendedRegistrationView(OneStepRegistrationView, ActivationEmailMixin):
    plain_email_body_template = "registration/activation_email_body.txt"
    html_email_body_template = "registration/activation_email_body.html"

    def register(self, form):
        new_user = super(ExtendedRegistrationView, self).register(form)
        self.send_activation_email(new_user)
        return new_user

    def send_activation_email(self, user):
        activation_key = self.get_activation_key(user)
        context = self.get_email_context(activation_key)
        context["user"] = user
        subject = render_to_string(
            template_name=self.email_subject_template,
            context=context,
            request=self.request,
        )
        subject = "".join(subject.splitlines())
        message = render_to_string(
            template_name=self.plain_email_body_template,
            context=context,
            request=self.request,
        )
        html_message = render_to_string(
            template_name=self.html_email_body_template,
            context=context,
            request=self.request,
        )
        user.email_user(subject, message, settings.DEFAULT_FROM_EMAIL, html_message=html_message)


class EmailActivationView(ActivationView):
    success_url = reverse_lazy("diggers:registration_activation_complete")

    def activate(self, *args, **kwargs):
        username = self.validate_key(kwargs.get("activation_key"))
        user = self.get_user(username)
        user.email_verified = True
        user.save()
        return user

    def get_user(self, username):
        try:
            user = User.objects.get(**{User.USERNAME_FIELD: username})
            if user.email_verified:
                raise ActivationError(
                    self.ALREADY_ACTIVATED_MESSAGE, code="already_activated"
                )
            return user
        except User.DoesNotExist:
            raise ActivationError(self.BAD_USERNAME_MESSAGE, code="bad_username")
