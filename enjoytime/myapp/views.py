import os
from django.conf import settings
from django.http import JsonResponse
import json
import base64
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes
from enjoytime.settings import sendResponse, connectDB, disconnectDB  # type: ignore
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile




def dt_class(request):
    jsons = json.loads(request.body)
    action = jsons['action']
    respData = [{"result": "ISSW"}]
    resp = sendResponse(action, 200, "Success", respData)
    return resp


# dt_addcat


def dt_addcategories(request):
    jsons = json.loads(request.body)
    action = jsons.get('action', 'addcategory')

    try:
        name = jsons['name']
    except KeyError:
        return JsonResponse(sendResponse(action, 1002, "Missing key: name", []))

    try:
        myConn = connectDB()
        cursor = myConn.cursor()

        # Шалгах: Давтагдсан нэр байгаа эсэхийг
        cursor.execute(
            "SELECT 1 FROM t_enjoycategories WHERE name = %s LIMIT 1", (name,))
        if cursor.fetchone():
            return JsonResponse(sendResponse(action, 1003, "Category with this name already exists", []))

        query = """
            INSERT INTO t_enjoycategories (name)
            VALUES (%s)
            RETURNING id
        """
        cursor.execute(query, (name,))
        new_id = cursor.fetchone()[0]
        myConn.commit()

        resp = sendResponse(
            action, 200, "Category added successfully", {"id": new_id})

    except Exception as e:
        myConn.rollback()
        resp = sendResponse(
            action, 1006, "Add category DB error: " + str(e), [])

    finally:
        cursor.close()
        disconnectDB(myConn)

    return JsonResponse(resp)


# dt_getaddplace


################

@csrf_exempt
def     dt_getaddplace(request):
    try:
        img = request.FILES.get('image')
        action = request.POST.get('action')
        name = request.POST.get('name')
        description = request.POST.get('description')
        location = request.POST.get('location')
        # Expecting base64 encoded image
        image_data = request.POST.get('image')
        category_id = request.POST.get('category_id')
    except Exception as e:
        data = [{"error": str(e)}]
        result = sendResponse(404, data, "updateResume")
        return result
    try:
        if img:
            image_name = img.name

            # Зургийг хадгалах
            image_path = default_storage.save(
                f'images/{image_name}', ContentFile(img.read()))

            # Хадгалсан зургийн URL буцаах
            image_url = default_storage.url(image_path)

            zuragZam = f'http://127.0.0.1:8000{image_url}'


        if not all([action, name, description, location, img, category_id]):
            return sendResponse(action, 400, "Missing required fields", [])
        
        with connectDB() as con:
            cur = con.cursor()
            query = """
            INSERT INTO t_enjoyplaces (name, description, location, image, category_id, created_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id
                """
            cur.execute(query, (name, description,
                        location, zuragZam, category_id, ))

            con.commit()
            new_place_id = cur.fetchone()[0]

            respData = [{"id": new_place_id}]
            resp = sendResponse(action, 200, "Success", respData)
            return resp
    except Exception as e:
        print(f'###################{e}')
        resp = sendResponse(action, 400, "server aldaa",[])
        return resp



    #####################
    # dt_registeruser
    
def dt_registeruser(request):
    jsons = json.loads(request.body)
    action = jsons['action']
    username = jsons["username"]
    email = jsons["email"]
    password = jsons["password"]

    try:
        myConn = connectDB()
        cursor = myConn.cursor()
        
        query = """
            INSERT INTO t_enjoyusers (username, email, password)
            VALUES (%s, %s, %s)
            RETURNING id
        """
        cursor.execute(query, (username, email, password))
        
        columns = cursor.description
        respRow = [
            {columns[index][0]: column for index, column in enumerate(row)}
            for row in cursor.fetchall()
        ]
        resp = sendResponse(action, 200, "Success", respRow)
        return resp 
    finally:
        cursor.close()
        disconnectDB(myConn)

############ getallplaces


def dt_getallplaces(request):
    import json
    jsons = json.loads(request.body)
    action = jsons.get('action')

    try:
        myConn = connectDB()
        cursor = myConn.cursor()

        query = """
        SELECT 
            p.id,
            p.name,
            p.location,
            p.description,
            p.image,
            c.name AS category_name,
            COALESCE(
                (
                    SELECT json_agg(
                        json_build_object('rating', r.score, 'comment', r.comment)
                    )
                    FROM t_enjoyratings r
                    WHERE r.place_id = p.id
                ), '[]'::json
            ) AS ratings
        FROM t_enjoyplaces p
        LEFT JOIN t_enjoycategories c ON p.category_id = c.id
        ORDER BY p.id DESC
        """

        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        data = []
        for row in rows:
            record = dict(zip(columns, row))
            data.append(record)

        resp = sendResponse(action, 200, "Success", data)
    except Exception as e:
        myConn.rollback()
        resp = sendResponse(action, 1006, f"getdata database error: {str(e)}", [])
    finally:
        cursor.close()
        disconnectDB(myConn)
        return resp

    
    ###############
def dt_showcategories(request):
    jsons = json.loads(request.body)
    action = jsons.get('action')

    try:
        myConn = connectDB()
        cursor = myConn.cursor()
        query = "SELECT * FROM t_enjoycategories"
        cursor.execute(query)
        columns = cursor.description
        respRow = [
            {columns[index][0]: column for index, column in enumerate(row)}
            for row in cursor.fetchall()
        ]
        resp = sendResponse(action, 200, "Success", respRow)
        myConn.rollback()
        resp = sendResponse(action, 1006, "getdata database error: " + str(e), [])
    finally:
        cursor.close()
        disconnectDB(myConn)
        return resp

#############

@permission_classes([IsAuthenticated])  # Ensure the user is authenticated

def dt_addrating(request):
    jsons = json.loads(request.body)
    action = jsons['action']
    user_id = jsons['user_id']
    place_id = jsons['place_id']
    score = jsons['score']
    comment = jsons['comment']

    user_id = request.user.id  # Get the authenticated user's ID

    try:
        # Validate score
        if score < 1 or score > 5:
            return sendResponse(action, 1001, "Score must be between 1 and 5", [])

        myConn = connectDB()
        cursor = myConn.cursor()

        # Check if the user has already rated the place
        check_query = """
            SELECT * FROM t_enjoyratings
            WHERE user_id = %s AND place_id = %s
        """
        cursor.execute(check_query, (user_id, place_id))
        existing_rating = cursor.fetchone()

        if existing_rating:
            return sendResponse(action, 1002, "You have already rated this place", [])

        # Insert new rating and comment
        query = """
            INSERT INTO t_enjoyratings (user_id, place_id, score, comment, created_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id
        """
        cursor.execute(query, (user_id, place_id, score, comment))

        # Get the ID of the newly created rating
        new_rating_id = cursor.fetchone()[0]

        respData = [{"id": new_rating_id}]
        resp = sendResponse(action, 200, "Rating and Comment added successfully", respData)
        return resp

    except Exception as e:
        # Handle errors
        return sendResponse(action, 1006, "Error occurred: " + str(e), [])
    
    finally:
        cursor.close()
        disconnectDB(myConn)


###########################

def dt_getratings(request):
    try:
        data = json.loads(request.body)
        action = data.get('action')
        place_id = data.get('place_id')

        if not place_id:
            return sendResponse(action, 1003, "place_id шаардлагатай", [])

        myConn = connectDB()
        cursor = myConn.cursor()

        query = """
            SELECT u.username, r.score, r.comment, r.created_at
            FROM t_enjoyratings r
            JOIN t_enjoyusers u ON r.user_id = u.id
            WHERE r.place_id = %s
            ORDER BY r.created_at DESC
        """
        cursor.execute(query, (place_id,))
        rows = cursor.fetchall()

        ratings = []
        for row in rows:
            ratings.append({
                "username": row[0],
                "score": row[1],
                "comment": row[2],
                "created_at": row[3].strftime("%Y-%m-%d %H:%M:%S"),
            })

        return sendResponse(action, 200, "Амжилттай", ratings)

    except Exception as e:
        return sendResponse("getratings", 1004, f"Алдаа: {str(e)}", [])

    finally:
        cursor.close()
        disconnectDB(myConn)
            
############## login


def dt_loginuser(request):
    if request.method != "POST":
        return sendResponse("login", 405, "Only POST method allowed", [])

    try:
        jsons = json.loads(request.body)
        action = jsons.get("action", "login")
        email = jsons["email"]
        password = jsons["password"]

        myConn = connectDB()
        cursor = myConn.cursor()

        query = """
            SELECT id, username, email 
            FROM t_enjoyusers
            WHERE email = %s AND password = %s
        """
        cursor.execute(query, (email, password))
        rows = cursor.fetchall()

        if rows:
            columns = [desc[0] for desc in cursor.description]
            user_data = [{columns[i]: value for i, value in enumerate(row)} for row in rows]
            return sendResponse(action, 200, "Login successful", user_data)
        else:
            return sendResponse(action, 401, "Invalid email or password", [])

    except Exception as e:
        return sendResponse("login", 500, f"Server error: {str(e)}", [])
    finally:
        cursor.close()
        disconnectDB(myConn)
        
        
        #####################
        
        
        
    

@csrf_exempt
def checkService(request):
    if request.method == "POST":
        if request.content_type.startswith("multipart/form-data"):
            action = request.POST.get('action')
            if not action:
                res = sendResponse(4009)
                return JsonResponse(res)
            if action == 'getaddplace':
                result = dt_getaddplace(request)
                return JsonResponse(result)
            else:
                result = sendResponse(4003)
                return JsonResponse(result)
        else:
            content_type = request.content_type  
            if content_type == 'application/json': #raw json
                try:
                    jsons = json.loads( request.body)
                except: 
                    action = "invalid request json"
                    respData = []
                    resp = sendResponse(action, 404, "Error", respData)
                    return (JsonResponse(resp))
                # print(jsons)
                try: 
                    action = jsons['action']
                except:
                    action = "no action"
                    respData = []
                    resp = sendResponse(action, 400,"Error", respData)
                    return (JsonResponse(resp))
                
                # print(action)
                if(action == 'class'): #
                    result = dt_class(request)
                    return (JsonResponse(result))
                elif(action == 'getallplaces'):
                    result = dt_getallplaces(request)
                    return JsonResponse(result)
                elif(action == 'getaddplace'):
                    result = dt_getaddplace(request)
                    return (JsonResponse(result))
                elif(action == 'registeruser'):
                    result = dt_registeruser(request)
                    return (JsonResponse(result))
                elif(action == 'showcategories'):
                    result = dt_showcategories(request)
                    return (JsonResponse(result))
                elif(action == 'addrating'):
                    result = dt_addrating(request)
                    return (JsonResponse(result))
                elif(action == 'showratings'):
                    result = dt_getratings(request)
                    return (JsonResponse(result))
                elif(action == 'login'):
                    result = dt_loginuser(request)
                    return (JsonResponse(result))


                elif action == 'addcategory':
                    result = dt_addcategories(request)  # Функцийн нэрээ зөв тохируулна уу
                    return result  # JsonResponse-оор аль хэдийнэ ороод ирсэн гэж үзэж байна
                else:
                        action = action
                        respData = []
                        resp = sendResponse(action, 406,"Error", respData)
                        return (JsonResponse(resp))
            elif request.method == "GET":
                return (JsonResponse({ "method":"GET" }))
            else :
                return (JsonResponse({ "method":"busad" }))
            


