#!/usr/bin/python
# -*- coding: utf-8 -*-
from django.contrib.auth.models import User
from django.conf import settings
from django.shortcuts import render
import simplejson as json
from datetime import datetime,date
from coronae import Coronae,append_path
append_path()

import requests
import tornado.web,time,ast
from forms import *
from models import *
from tornado.auth import FacebookGraphMixin
from tornado import httpclient

from core.stream import *
from core.social import *
from core.models import *
from core.forms import *
from core.views import *
from play.models import *
from create.models import *
from core.social import *

objs = json.load(open('objects.json','r'))

def init_spread(request):
    return render(request,'spreads.html',{'static_url':settings.STATIC_URL},content_type='text/html')    

def main(request):
    graph = SocialGraph()
    if request.method == 'GET': 
        return graph.view_spread(request)
    elif request.method == 'POST': 
        return graph.create_spread(request)
    
def event(request):
    graph = SocialGraph()
    if request.method == 'GET':
        return graph.view_event(request)
    elif request.method == 'POST':
        return graph.create_event(request)

def content(request):
    return render(request,'contents.html',{'static_url':settings.STATIC_URL},content_type='text/html')

class Social(Efforia):
    def __init__(self): pass
    def view_spread(self,request):
        if 'view' in request.GET:
            strptime,token = request.GET['object'].split(';')
            now,obj,rel = self.get_object_bydate(strptime,token)
            spreaded = globals()[rel].objects.all().filter(date=now)[0]
            feed = []; feed.append(spreaded.spreaded)
            spreads = globals()[rel].objects.all().filter(spreaded=spreaded.spreaded)
            for s in spreads: feed.append(s.spread)
            self.render_grid(feed)
        else:
            tutor = True
            #if not self.authenticated(): return
            if 'spread' in request.GET: tutor = False
            form = SpreadForm()
            return render(request,"spread.html",{'form':form,'tutor':tutor},content_type='text/html')
    def create_spread(self,request):
        u = self.current_user(request)
        if 'spread' in request.POST:
            c = request.POST['spread'][0]
            spread = Spreadable(user=u,content=c,name='!'+u.username)
            spread.save()
            strptime,token = request.POST['time'][0].split(';')
            now,objs,rels = self.get_object_bydate(strptime,token)
            o = globals()[objs].objects.all().filter(date=now)[0]
            relation = globals()[rels](spreaded=o,spread=spread,user=u)
            relation.save()
            spreads = []; spreads.append(o)
            spreadablespreads = globals()[rels].objects.all().filter(spreaded=o,user=u)
            for s in spreadablespreads: spreads.append(s.spread)
        else:
            spread = self.spread_post(request)
            spread.save()
            spreads = Spreadable.objects.all().filter(user=u)
        feed = []
        self.accumulate_points(1,request)
        for s in spreads: feed.append(s)
        feed.sort(key=lambda item:item.date,reverse=True)
        return self.render_grid(feed,request)
    def spread_post(self,request):
        name = self.current_user(request).first_name.lower()
        text = unicode('%s !%s' % (request.POST['content'],name))
        user = self.current_user(request)
        post = Spreadable(user=user,content=text,name='!'+name)
        return post
    
class SocialGraph(Social,FacebookGraphMixin):
    def __init__(self): pass
    def view_event(self,request):
        if 'view' in request.GET:
            strptime,token = request.GET['object'].split(';')
            now,obj,rel = self.get_object_bydate(strptime,token)
            spreaded = globals()[rel].objects.all().filter(date=now)[0]
            feed = []; feed.append(spreaded.spreaded)
            spreads = globals()[rel].objects.all().filter(spreaded=spreaded.spreaded)
            for s in spreads: feed.append(s.spread)
            self.render_grid(feed)
        else:
            form = EventForm()
            form.fields['name'].label = 'Nome'
            form.fields['start_time'].label = 'Início'
            form.fields['end_time'].label = 'Fim'
            form.fields['location'].label = 'Local'
            return render(request,'event.html',{'static_url':settings.STATIC_URL,'form':form},content_type='text/html')
    def create_event(self,request):
        name = request.POST['name']
        local = request.POST['location']
        times = request.POST['start_time'],request.POST['end_time']
        dates = []
        for t in times: 
            strp_time = time.strptime(t,'%d/%m/%Y')
            dates.append(datetime.fromtimestamp(time.mktime(strp_time)))
        event_obj = Event(name='@@'+name,user=self.current_user(request),start_time=dates[0],
                          end_time=dates[1],location=local,id_event='',rsvp_status='')
        event_obj.save()
        self.accumulate_points(1,request)
        events = Event.objects.all().filter(user=self.current_user(request))
        return render(request,'grid.jade',{'f':events},content_type='text/html')

class Register(Coronae,GoogleHandler,TwitterHandler,FacebookHandler,tornado.auth.TwitterMixin,tornado.auth.FacebookGraphMixin):
    @tornado.web.asynchronous
    def get(self):
        google_id = self.get_argument("google_id",None)
        google = self.get_argument("google_token",None)
        twitter_id = self.get_argument("twitter_id",None)
        twitter = self.get_argument("twitter_token",None)
        facebook = self.get_argument("facebook_token",None)
        self.google_token = self.twitter_token = self.facebook_token = response = ''
        google = 'empty' if not google else google
        if 'empty' not in google:
            if self.get_current_user():
                profile = Profile.objects.all().filter(user=self.current_user())[0]
                profile.google_token = google
                profile.save()
                self.redirect('/')
            else:
                if len(User.objects.all().filter(username=google_id)) > 0: return
                profile = self.google_credentials(google)
                profile['google_token'] = google
                self.google_enter(profile,False)
        if google_id:
            user = User.objects.all().filter(username=google_id)
            if len(user) > 0:
                token = user[0].profile.google_token
                profile = self.google_credentials(token) 
                self.google_enter(profile)
            else:
                self.approval_prompt()
        if twitter:
            user = User.objects.all().filter(username=twitter_id)
            prof = ast.literal_eval(str(twitter))
            if len(user) > 0: self.twitter_enter(prof)
            elif not self.get_current_user():
                self.twitter_token = prof 
                self.twitter_credentials(twitter)
            else:
                profile = Profile.objects.all().filter(user=self.current_user())[0]
                profile.twitter_token = prof['key']+';'+prof['secret']
                profile.save()
                self.redirect('/')
        elif facebook: 
            prof = Profile.objects.all().filter(facebook_token=facebook)
            if len(prof) > 0: self.facebook_token = self.facebook_credentials(facebook)
            elif not self.get_current_user(): self.facebook_token = self.facebook_credentials(facebook)
            else:
                profile = Profile.objects.all().filter(user=self.current_user())[0]
                profile.facebook_token = facebook
                profile.save()
                self.redirect('/')
        else:
            self._on_response(response)
    def google_enter(self,profile,exist=True):
        if not exist:
            age = date.today()
            contact = profile['link'] if 'link' in profile else ''
            data = {
                    'username':     profile['id'],
                    'first_name':   profile['given_name'],
                    'last_name':    profile['family_name'],
                    'email':        contact,
                    'google_token': profile['google_token'],
                    'password':     '3ff0r14',
                    'age':          age        
            }
            self.create_user(data)
        self.login_user(profile['id'],'3ff0r14')
    def twitter_enter(self,profile,exist=True):
        if not exist:
            age = date.today()
            names = profile['name'].split()[:2]
            given_name,family_name = names if len(names) > 1 else (names[0],'')
            data = {
                    'username':     profile['user_id'],
                    'first_name':   given_name,
                    'last_name':    family_name,
                    'email':        '@'+profile['screen_name'],
                    'twitter_token': profile['key']+';'+profile['secret'],
                    'password':     '3ff0r14',
                    'age':          age        
            }
            self.create_user(data)
        self.login_user(profile['user_id'],'3ff0r14')
    def facebook_enter(self,profile,exist=True):
        if not exist:
            strp_time = time.strptime(profile['birthday'],"%m/%d/%Y")
            age = datetime.fromtimestamp(time.mktime(strp_time))
            if 'first_name' not in profile:
                names = profile['name'].split()[:2]
                profile['first_name'],profile['last_name'] = names if len(names) > 1 else (names[0],'')
            data = {
                'username':   profile['id'],
                'first_name': profile['first_name'],
                'last_name':  profile['last_name'],
                'email':      profile['link'],
                'facebook_token': self.facebook_token,
                'password':   '3ff0r14',
                'age':        age
            }
            self.create_user(data)
        self.login_user(profile['id'],'3ff0r14')
    def _on_twitter_response(self,response):
        if response is '': return
        profile = self.twitter_token
        prof = ast.literal_eval(str(response))
        profile['name'] = prof['name']
        self.twitter_enter(profile,False)
    def _on_facebook_response(self,response):
        if response is '': return
        profile = ast.literal_eval(str(response))
        user = User.objects.all().filter(username=profile['id'])
        if len(user) > 0: self.facebook_enter(profile)
        else: self.facebook_enter(profile,False)
    def _on_response(self,response):
        form = RegisterForm()
        return self.render(self.templates()+"simpleform.html",form=form,submit='Entrar',action='register')
    @tornado.web.asynchronous
    def post(self):
        data = {
            'username':self.request.arguments['username'][0],
            'email':self.request.arguments['email'][0],
            'password':self.request.arguments['password'][0],
            'last_name':self.request.arguments['last_name'][0],
            'first_name':self.request.arguments['first_name'][0]
        }
        form = RegisterForm(data=data)
        if len(User.objects.filter(username=self.request.arguments['username'][0])) < 1:
            strp_time = time.strptime(self.request.arguments['birthday'][0],"%m/%d/%Y")
            birthday = datetime.fromtimestamp(time.mktime(strp_time)) 
            form.data['age'] = birthday
            self.create_user(form.data)
        username = self.request.arguments['username'][0]
        password = self.request.arguments['password'][0]
        self.login_user(username,password)
    def create_user(self,data):
        user = User.objects.create_user(data['username'],
                                        data['email'],
                                        data['password'])
        user.last_name = data['last_name']
        user.first_name = data['first_name']
        user.save()
        google_token = twitter_token = facebook_token = ''
        if 'google_token' in data: google_token = data['google_token']
        elif 'twitter_token' in data: twitter_token = data['twitter_token']
        elif 'facebook_token' in data: facebook_token = data['facebook_token']
        profile = Profile(user=user,birthday=data['age'],
                          twitter_token=twitter_token,
                          facebook_token=facebook_token,
                          google_token=google_token)
        profile.save()
    def login_user(self,username,password):
        auth = self.authenticate(username,password)
        if auth is not None:
            self.set_cookie("user",tornado.escape.json_encode(username))
            self.redirect("/")
        else:
            error_msg = u"?error=" + tornado.escape.url_escape("Falha no login")
            self.redirect(u"/login" + error_msg)
    def authenticate(self,username,password):
        exists = User.objects.filter(username=username)
        if exists:
            if exists[0].check_password(password):
                return 1
        else: return None

class TwitterPosts(Coronae,TwitterHandler):
    def get(self):
        name = self.current_user().username
        text = unicode('%s !%s' % (self.request.arguments['content'][0],name))
        limit = 135-len(name)
        if len(self.request.arguments['content']) > limit: 
            short = unicode('%s... !%s' % (self.request.arguments['content'][0][:limit],name))
        else: short = text
        twitter = self.current_user().profile.twitter_token
        if not twitter: twitter = get_offline_access()['twitter_token']
        access_token = self.format_token(twitter)
        encoded = short.encode('utf-8')
        self.twitter_request(
            "/statuses/update",
            post_args={"status": encoded},
            access_token=access_token,
            callback=self.async_callback(self.posted))
        self.write('Postagem tuitada com sucesso.')
    def posted(self,response): pass

class FacebookPosts(Coronae,FacebookHandler):
    def get(self):
        facebook = self.current_user().profile.facebook_token
        if facebook:
            name = self.current_user().username
            text = unicode('%s !%s' % (self.request.arguments['content'],name))
            encoded_facebook = text.encode('utf-8')
            self.facebook_request("/me/feed",post_args={"message": encoded_facebook},
                              access_token=facebook,
                              callback=self.async_callback(self.posted))
            self.write('Postagem publicada com sucesso.')
    def posted(self,response): pass
    
class FacebookEvents(Coronae,FacebookHandler):
    def get(self):
        name = self.request.arguments['name'][0]
        times = self.request.arguments['start_time'][0],self.request.arguments['end_time'][0]
        dates = []
        for t in times: 
            strp_time = time.strptime(t,'%d/%m/%Y')
            dates.append(datetime.fromtimestamp(time.mktime(strp_time)))
        facebook = self.current_user().profile.facebook_token
        if facebook:
            args = { 'name':name, 'start_time':dates[0], 'end_time':dates[1] }
            self.facebook_request("/me/events",access_token=facebook,post_args=args,
                                  callback=self.async_callback(self.posted))
    def posted(self): pass