import json
import re
from typing import Any
from datetime import datetime
from pydantic import BaseModel
class hoteltrip(BaseModel):
    Name: str
    HotelId: int
    Basic_info: dict
    location: dict[str, str|int]
    Nearby_location:list[dict]
    Roomdetails:list[dict]
    Customer_reviews_data:list[dict[str,Any]]
    Ratingdata:list[dict[str,Any]]
    Policy: dict
    Recommendations:dict[str,list[dict[str,str]]] = None
# load and dump main file
def load_main_file(file):
    with open(file,"rb") as f:
        data=json.loads(f.read().decode())
        return data
def dump_main_file(json_data):
    with open("cleandata.json","wb") as f:
        f.write(json.dumps(json_data, indent=4,ensure_ascii=False).encode())
# load and dump clean file and process
def load_clean_file(file):
    with open(file,"rb") as f:
        data=json.loads(f.read().decode())
        return data


def parser(d):
    s_dict = {}
    Customer_reviews_data = []
    reviews__ratings_base_path = d.get("hotelDetailResponse", {}).get("hotelComment", {}).get("comment", {})
    recommed_name = d["seoSSRData"]["seoFooterModule"]["title"]

    if isinstance(d, dict):
        path = d.get("hotelDetailResponse").get("hotelBaseInfo")
        if isinstance(path, dict):
            s_dict["Name"] = path.get("hotelNames")[0]
            s_dict["HotelId"] = d.get("ssrHotelRoomListRequest").get("search").get("hotelId")
            sub_path = d.get("hotelDetailResponse").get("hotelDescriptionInfo")
            address_path = d.get("hotelDetailResponse").get("hotelPositionInfo").get("address")
            room_path = sub_path.get("lables")
            phone_path = sub_path.get("tels")
            basic_info = {
                "Number_of_room": room_path[1][17:21],
                "OpenYear": room_path[0][8:13],
                "PhoneNo": phone_path[0].get("show"),
                "Description": sub_path.get("description")
            }
            s_dict["Basic_info"] = basic_info
            # location
            s_dict["location"] = {
                "Address": address_path,
                "City": path.get("cityName"),
                "State": path.get("provinceName"),
                "Country": path.get("countryName"),
                "Pincode": int(re.search(r"\d{6}", address_path).group())
            }
            # Policy
            po = d.get("hotelDetailResponse").get("hotelPolicyInfo").get("checkInAndOut").get("content")
            b = d.get("hotelDetailResponse").get("hotelPolicyInfo").get("breakfast").get("content")
            breakfast_dict = {
                "Timeing": b[1].get("description"),
                "price": b[2].get("tab").get("tableItems")[0].get("tableDetails")[1].get("content")[9:]
            }
            policy_dict = {
                "checkIn": po[0].get("description"),
                "checkOut": po[1].get("description"),
                "frontdeskhours": po[2].get("description"),
                "Breakfast": breakfast_dict
            }
            s_dict["Policy"] = policy_dict
            # nearby locations
            nearby = []
            nearby_name = d.get("hotelDetailResponse").get("hotelPositionInfo").get("placeInfo").get("wholePoiInfoList")
            for item in nearby_name:
                if isinstance(item, dict):
                    nearby.append({
                        "distance": item.get("distance"),
                        "dist_type": item.get("distType"),
                        "Name": item.get("poiName")
                    })
            s_dict["Nearby_location"] = nearby

        # room details (removing duplication)
        result = []
        rooms = d.get('hotelCommentResponse').get('commentStaticInfo').get('roomList')
        picture_facility_path = d.get('seoSSRData').get('seoHotelRooms').get('physicRoomMap')

        for room in rooms:
            if not room:
                continue
            room_id = room.get('id')
            room_name = room.get('name')
            if not room_id:
                continue
            room_info = {
                "id": room_id,
                "name": room_name,
                "url": [],
                "facilitys": []
            }
            room_pictures = picture_facility_path.get(str(room_id), {}).get('pictureInfo', [])
            facility_path = picture_facility_path.get(str(room_id), {}).get('baseFacilityInfo', [])
            bedInfo = picture_facility_path.get(str(room_id), {}).get('bedInfo', {})
            more_facility_list = picture_facility_path.get(str(room_id), {}).get('newFacilityList')

            # Adding pictures to room_info
            for pic in room_pictures:
                url = pic.get('url')
                if url:
                    room_info["url"].append(url)

            # Adding facilities to room_info
            for facility in facility_path:
                title = facility.get('title')
                if title:
                    room_info['facilitys'].append(title)

            bed_title = bedInfo.get('title')
            if bed_title:
                room_info['facilitys'].append(bed_title)

            for more in more_facility_list:
                more_list = more.get('title')
                if more_list:
                    room_info['facilitys'].append(more_list)

            # Only append room_info once
            result.append(room_info)

        s_dict["Roomdetails"] = result

    # Rating section
    for review in reviews__ratings_base_path.get("positiveDirection", []):
        temp_review = {
            "Guest_Name": review.get("userInfo").get("nickName"),
            "Guest_id": review.get("id"),
            "Comment": review.get("content"),
            "Guest_Profile": review.get("userInfo").get("headPictureUrl")
        }
        Customer_reviews_data.append(temp_review)
        s_dict["Customer_reviews_data"] = Customer_reviews_data

    Rating_data = []
    rating_path = reviews__ratings_base_path.get("scoreDetail", [])
    for rate in rating_path:
        temp_rating = {
            "Category": rate.get("showName"),
            "Rating": rate.get("showScore")
        }
        Rating_data.append(temp_rating)
    s_dict["Ratingdata"] = Rating_data

    # Recommendations
    s_dict[recommed_name] = {}
    most_view_name = d["seoSSRData"]["seoFooterModule"]["footerItem"][0]["title"].replace(" ", "_")
    s_dict[recommed_name][most_view_name] = []
    most_viewe_list = d["seoSSRData"]["seoFooterModule"]["footerItem"][0]["linkItem"]

    for data in most_viewe_list:
        hotal_dict = {}
        hotal_dict["hotel_name"] = data["text"]
        hotal_dict["hotel_url"] = data["url"]
        s_dict[recommed_name][most_view_name].append(hotal_dict)

    validated_model = hoteltrip.model_validate(s_dict)
    return validated_model
def write_file(file):
    file_name = datetime.now().strftime("%Y-%m-%d")
    with open(f"Trip_Hotel_{file_name}.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(file.model_dump(), indent=4, ensure_ascii=False))
# this is for load and clening data
file_name=r"C:\Users\vishal.mistry\Desktop\Mistry Vishal\hoteltrip\trip_hotel.json"
file_data=load_main_file(file_name)
inner_data=file_data[1]
clean_string = inner_data.replace("Jc:", "", 1)
hotel_data = json.loads(clean_string)
main_data=hotel_data[3]
dump_main_file(main_data)
# this is load cleaning data and dump
user_file_input=r"C:\Users\vishal.mistry\Desktop\Mistry Vishal\hoteltrip\cleandata.json"
a = load_main_file(user_file_input)
b = parser(a)
write_file(b)

