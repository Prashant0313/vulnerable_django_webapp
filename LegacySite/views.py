import json
from django.db.utils import IntegrityError
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from LegacySite.models import User, Product, Card
from . import extras
from django.views.decorators.csrf import csrf_protect as csrf_protect
from django.contrib.auth import login, authenticate, logout
from django.core.exceptions import ObjectDoesNotExist
import os, tempfile, re
from fernet_fields import *

SALT_LEN = 16

# Create your views here.
# Landing page. Nav bar, most recently bought cards, etc.
def index(request): 
    context= {'user': request.user}
    return render(request, "index.html", context)

# Register for the service.
@csrf_protect #[rtb325]
def register_view(request):
    if request.method == 'GET':
        return render(request, "register.html", {'method':'GET'})
    else:
        context = {'method':'POST'}
        uname = request.POST.get('uname', None)
        pword = request.POST.get('pword', None)
        pword2 = request.POST.get('pword2', None)
        # if registered user exists error fix [rtb325]
        try:
            User.objects.get(username=uname)
            if User.objects.get(username=uname) is not None:
                context["success"] = False
                return render(request, "register.html", context)
        except:
            pass
        assert (None not in [uname, pword, pword2])
        # blank user and pass fix [rtb325]
        if pword != pword2 or uname == "" or pword== "":
            context["success"] = False
            return render(request, "register.html", context)
        salt = extras.generate_salt(SALT_LEN)
        hashed_pword = extras.hash_pword(salt, pword)
        hashed_pword = salt.decode('utf-8') + '$' + hashed_pword
        u = User(username=uname, password=hashed_pword)
        u.save()
        return redirect("index.html")
        

# Log into the service.
@csrf_protect #[rtb325]
def login_view(request):
    if request.method == "GET":
        return render(request, "login.html", {'method':'GET', 'failed':False})
    else:
        context = {'method':'POST'}
        uname = request.POST.get('uname', None)
        pword = request.POST.get('pword', None)
        assert (None not in [uname, pword])
        user = authenticate(username=uname, password=pword)
        if user is not None:
            context['failed'] = False
            login(request, user)
            print("Logged in user")
        else:
            context['failed'] = True
            return render(request, "login.html", context)
        return redirect("index.html")

# Log out of the service.
def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
    return redirect("index.html")

@csrf_protect #[rtb325]
def buy_card_view(request, prod_num=0):
    if request.method == 'GET':
        context = {"prod_num" : prod_num}
        director = request.GET.get('director', None)
        if director is not None:
            # KG: Wait, what is this used for? Need to check the template.
            context['director'] = director
        if prod_num != 0:
            try:
                prod = Product.objects.get(product_id=prod_num) 
            except:
                return HttpResponse("ERROR: 404 Not Found.")
        else:
            try:
                prod = Product.objects.get(product_id=1) 
            except:
                return HttpResponse("ERROR: 404 Not Found.")
        context['prod_name'] = prod.product_name
        context['prod_path'] = prod.product_image_path
        context['price'] = prod.recommended_price
        context['description'] = prod.description
        return render(request, "item-single.html", context)
    elif request.method == 'POST':
        # buy when not logged in fix [rtb325]
        if not request.user.is_authenticated:
            return redirect("/login.html")
        if prod_num == 0:
            prod_num = 1
        num_cards = len(Card.objects.filter(user=request.user))
        # Generate a card here, based on amount sent. Need binary for this.
        card_file_path = os.path.join(tempfile.gettempdir(), f"addedcard_{request.user.id}_{num_cards + 1}.gftcrd")
        card_file_name = "newcard.gftcrd"
        # Use binary to write card here.
        # Create card record with data.
        # For now, until we get binary, write random data.
        prod = Product.objects.get(product_id=prod_num)
        amount = request.POST.get('amount', None)
        if amount is None or amount == '':
            amount = prod.recommended_price
        extras.write_card_data(card_file_path, prod, amount, request.user)
        card_file = open(card_file_path, 'rb')
        card = Card(data=card_file.read(), product=prod, amount=amount, fp=card_file_path, user=request.user)
        card.save()
        card_file.seek(0)
        response = HttpResponse(card_file, content_type="application/octet-stream")
        response['Content-Disposition'] = f"attachment; filename={card_file_name}"
        return response
        #return render(request, "item-single.html", {})
    else:
        return redirect("/buy/1")

# KG: What stops an attacker from making me buy a card for him?
@csrf_protect #[rtb325]
def gift_card_view(request, prod_num=0):
    context = {"prod_num" : prod_num}
    # CSRF 'get' protection
    if request.method == "GET" and ('username' not in request.GET or 'password' not in request.GET):
        request.GET.get('director', None)
        context['user'] = None
        director = request.GET.get('director', None)
        if director is not None:
            context['director'] = director
        if prod_num != 0:
            try:
                prod = Product.objects.get(product_id=prod_num) 
            except:
                return HttpResponse("ERROR: 404 Not Found.")
        else:
            try:
                prod = Product.objects.get(product_id=1) 
            except:
                return HttpResponse("ERROR: 404 Not Found.")
        context['prod_name'] = prod.product_name
        context['prod_path'] = prod.product_image_path
        context['price'] = prod.recommended_price
        context['description'] = prod.description
        return render(request, "gift.html", context)
    # Hack: older partner sites only support GET, so special case this.
    # CSRF Fix [rtb325]: double protect 'POST' with csrf tokens
    elif request.method == "POST":
        if not request.user.is_authenticated:
            return redirect("/login.html")
        if prod_num == 0:
            prod_num = 1
        # Get vars from post
        user = request.POST.get('username', None) 
        amount = request.POST.get('amount', None) 
        if user is None:
            return HttpResponse("ERROR 404")
        try:
            user_account = User.objects.get(username=user)
        except:
            user_account = None
        if user_account is None:
            context['user'] = None
            return render(request, f"gift.html", context)
        context['user'] = user_account
        num_cards = len(Card.objects.filter(user=user_account))
        card_file_path = os.path.join(tempfile.gettempdir(), f"addedcard_{user_account.id}_{num_cards + 1}.gftcrd")
        #extras.write_card_data(card_file_path)
        prod = Product.objects.get(product_id=prod_num)
        if amount is None or amount == '':
            amount = prod.recommended_price
        extras.write_card_data(card_file_path, prod, amount, request.user)
        prod = Product.objects.get(product_id=prod_num)
        card_file = open(card_file_path, 'rb')
        card_data = card_file.read()
        card = Card(data=card_data, product=prod,
                    amount=amount, fp=card_file_path, user=user_account)
       
        card.save()
        card_file.close()
        return render(request, f"gift.html", context)
    # CSRF Fix [rtb325]: protect 'GET' URL with password
    elif request.method == "GET" and 'username' in request.GET and 'password' in request.GET:
        if not request.user.is_authenticated:
            return redirect("/login.html")
        if prod_num == 0:
            prod_num = 1
        # Get vars from get
        usr = request.GET.get('username', None)
        pw = request.GET.get('password', None)
        if usr is None or pw is None:
            return HttpResponse("ERROR 404")
        try:
            success = authenticate(username=request.user, password=pw)
            user_account = User.objects.get(username=usr)
        except:
            success = None
            user_account = None
        if user_account is None or success is None:
            context['user'] = None
            return render(request, f"gift.html", context)
        context['user'] = user_account
        num_cards = len(Card.objects.filter(user=user_account))
        card_file_path = os.path.join(tempfile.gettempdir(), f"addedcard_{user_account.id}_{num_cards + 1}.gftcrd")
        #extras.write_card_data(card_file_path)
        prod = Product.objects.get(product_id=prod_num)
        amount = prod.recommended_price
        extras.write_card_data(card_file_path, prod, amount, request.user)
        prod = Product.objects.get(product_id=prod_num)
        card_file = open(card_file_path, 'rb')
        card_data = card_file.read()
        card = Card(data=card_data, product=prod,
                    amount=amount, fp=card_file_path, user=user_account)
        card.save()
        card_file.close()
        return render(request, f"gift.html", context)

@csrf_protect
def use_card_view(request):
    context = {'card_found': None}
    
    if request.method == "POST" and 'card_data' in request.FILES:
        card_file_data = request.FILES['card_data']
        card_fname = request.POST.get('card_fname', None)
        
        if card_fname is None or card_fname == '':
            card_file_path = os.path.join(tempfile.gettempdir(), f'newcard_{request.user.id}_parser.gftcrd')
        else:
            card_fname_check = card_fname.strip()
            card_fname_checked = re.sub(r'\W', '', card_fname_check)
            card_file_path = os.path.join(tempfile.gettempdir(), f'{card_fname_checked}_{request.user.id}_parser.gftcrd')
        
        card_data = card_file_data.read()
        
        try:
            card_data_json = json.loads(card_data)
            signature = card_data_json['records'][0]['signature']
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError):
            signature = extras.get_fake_signature(card_data)
        
        card_query = Card.objects.filter(data__icontains=signature)
        user_cards = Card.objects.filter(user=request.user, used=False)
        
        if not card_query.exists():
            if card_fname:
                card_file_path = os.path.join(tempfile.gettempdir(), f'{card_fname_checked}_{request.user.id}_{user_cards.count() + 1}.gftcrd')
            else:
                card_file_path = os.path.join(tempfile.gettempdir(), f'newcard_{request.user.id}_{user_cards.count() + 1}.gftcrd')
            
            with open(card_file_path, 'wb') as fp:
                fp.write(card_data)
            
            card = Card(data=card_data, fp=card_file_path, user=request.user, used=True)
            card.save()
        else:
            context['card_found'] = card_query.first()
        
        context['card'] = card  # Corrected context key
        return render(request, "use-card.html", context)

    return HttpResponse("Error: Bad Request", status=400)
