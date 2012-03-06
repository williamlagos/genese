#!/usr/bin/python
# -*- coding: utf-8 -*-
from django.contrib.auth.forms import AuthenticationForm
from models import UserProfile
from forms import RegisterForm,AuthorizeForm
from handlers import BaseHandler
import tornado.web
import tornado.auth
import urllib,urllib2
import simplejson as json

class LoginHandler(BaseHandler):    
    def get(self):
        form = AuthenticationForm()
        form.fields["username"].initial = "Nome do Usuário"
        form.fields["username"].label = form.fields["password"].label = ""
        self.render(self.templates()+"registration/login.html", next=self.get_argument("next","/"), form=form)
    def post(self):
        username = self.get_argument("username", "")
        password = self.get_argument("password", "")
        auth = self.authenticate(username,password) # DB lookup here
        if auth is not None:
            self.set_current_user(username)
            self.redirect(self.get_argument("next", "/"))
        else:
            error_msg = u"?error=" + tornado.escape.url_escape("Login incorrect.")
            self.redirect(u"/login" + error_msg)
    def set_current_user(self, user):
        if user:
            self.set_cookie("user",tornado.escape.json_encode(user))
        else:
            self.clear_cookie("user")

class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("user")
        self.redirect(u"/login")
        
class GoogleHandler(tornado.web.RequestHandler,tornado.auth.GoogleMixin):
    def get(self):
        if self.get_argument("oauth_token", None):
            self.get_authenticated_user(self.async_callback(self._on_auth)); return
        self.authorize_redirect("416575314846.apps.googleusercontent.com",
                                "http://efforia.herokuapp.com/oauth2callback",
                                "https://gdata.youtube.com&response_type=code")
    def _on_auth(self,user):
        if not user: raise tornado.web.HTTPError(500, "Google auth failed")
    def authorize_redirect(self,client_id,redirect_uri,scope):
        oauth2_url = "https://accounts.google.com/o/oauth2/auth?"
        redirect_uri = redirect_uri; client_id = client_id; scope = scope
        oauth2_url = "%sclient_id=%s&redirect_uri=%s&scope=%s&access_type=offline" % (oauth2_url,client_id,redirect_uri,scope)
        self.redirect(oauth2_url)

class OAuth2Handler(BaseHandler):
    def get(self):
        form = AuthorizeForm()
        form.fields["code"].initial = self.request.uri.split("=")[1:][0]
        data = urllib.urlencode({
      		'code': form["code"].value(),
    		'client_id': form["client_id"].value(),
    		'client_secret': form["client_secret"].value(),
    		'redirect_uri': form["redirect_uri"].value(),
    		'grant_type': 'authorization_code'
    	})
        request = urllib2.Request(
      	url='https://accounts.google.com/o/oauth2/token',
    	data=data)
        request_open = urllib2.urlopen(request)
    
        response = request_open.read()
        request_open.close()
        tokens = json.loads(response)
        access_token = tokens['access_token']
        self.set_cookie("token",tornado.escape.json_encode(access_token))
        self.redirect("/")
        
        #self.render(self.templates()+"empty.html",access=access_token,refresh=tokens)
        #http://gdata.youtube.com/feeds/api/users/default/uploads?access_token=ya29.AHES6ZSDqICBoPul6rHxctXCvy3Lld8P3YNOaWN029UhneT4

class FacebookHandler(LoginHandler, tornado.auth.FacebookGraphMixin):
    @tornado.web.asynchronous
    def initialize(self):
        self.settings["facebook_api_key"] = "153246718126522"
        self.settings["facebook_secret"] = "15f57d59a69b96c3d3013b4c9aa301f2"
    def get(self):
        self.initialize()
        if self.get_argument("code", False):
            self.get_authenticated_user(
				redirect_uri='/auth/facebookgraph/',
				client_id=self.settings["facebook_api_key"],
				client_secret=self.settings["facebook_secret"],
				code=self.get_argument("code"),
				callback=self.async_callback(
				self._on_login))
            return
        self.authorize_redirect(redirect_uri='/auth/facebookgraph/',
                              		client_id=self.settings["facebook_api_key"],
		                        extra_params={"scope": "read_stream,offline_access"})
    def _on_login(self, user):
        logging.error(user)
        self.finish()

class RegisterHandler(BaseHandler):
    def get(self):
        form = RegisterForm() # An unbound form
        return self.render(self.templates()+"registration/register.html",form=form)
    def post(self):
        data = {
            'username':self.request.arguments['username'][0],
            'email':self.request.arguments['email'][0],
            'password':self.request.arguments['password'][0],
            'last_name':self.request.arguments['last_name'][0],
            'first_name':self.request.arguments['first_name'][0],
            'age':self.request.arguments['age'][0],
        }
        form = RegisterForm(data=data)
        newuser = form.registerUser()
        profile = UserProfile(user=newuser,age=form.data['age'])
        profile.save()
        return self.redirect('/login') # Redirect after POST