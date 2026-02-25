import json
import re
from typing import Any
import mysql.connector
from mysql.connector import Error
from pydantic import BaseModel
from datetime import datetime


class hoteltrip(BaseModel):
    Name: str
    HotelId: int
    Basic_info: dict
    location: dict[str, str | int]
    Nearby_location: list[dict]
    Roomdetails: list[dict]
    Customer_reviews_data: list[dict[str, Any]]
    Ratingdata: list[dict[str, Any]]
    Policy: dict
    Recommendations: dict[str, list[dict[str, str]]] | None = None


def load_main_file(file):
    with open(file, "rb") as f:
        return json.loads(f.read().decode())


def write_file(file):
    file_name = datetime.now().strftime("%Y-%m-%d")
    with open(f"Trip_Hotel_{file_name}.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(file.model_dump(), indent=4, ensure_ascii=False))


def dump_main_file(json_data):
    with open("cleandata.json", "wb") as f:
        f.write(json.dumps(json_data, indent=4, ensure_ascii=False).encode())


def parser(d):
    s_dict = {}
    Customer_reviews_data = []

    hotel_detail = d.get("hotelDetailResponse", {})
    base_info = hotel_detail.get("hotelBaseInfo", {})
    description_info = hotel_detail.get("hotelDescriptionInfo", {})
    position_info = hotel_detail.get("hotelPositionInfo", {})
    policy_info = hotel_detail.get("hotelPolicyInfo", {})
    comment_data = hotel_detail.get("hotelComment", {}).get("comment", {})

    s_dict["Name"] = base_info.get("hotelNames", [""])[0]
    s_dict["HotelId"] = d.get("ssrHotelRoomListRequest", {}).get("search", {}).get("hotelId")

    labels = description_info.get("lables", [])
    tels = description_info.get("tels", [])

    number_of_rooms = labels[1][17:21] if len(labels) > 1 else None
    open_year = labels[0][8:13] if len(labels) > 0 else None
    phone = tels[0].get("show") if tels else None

    s_dict["Basic_info"] = {
        "Number_of_room": number_of_rooms,
        "OpenYear": open_year,
        "PhoneNo": phone,
        "Description": description_info.get("description")
    }

    address = position_info.get("address", "")
    pincode_match = re.search(r"\d{6}", address)

    s_dict["location"] = {
        "Address": address,
        "City": base_info.get("cityName"),
        "State": base_info.get("provinceName"),
        "Country": base_info.get("countryName"),
        "Pincode": pincode_match.group() if pincode_match else None
    }

    checkin_out = policy_info.get("checkInAndOut", {}).get("content", [])
    breakfast_content = policy_info.get("breakfast", {}).get("content", [])

    breakfast_dict = {}

    if len(breakfast_content) > 2:
        price_raw = breakfast_content[2].get("tab", {}).get("tableItems", [{}])[0] \
            .get("tableDetails", [{}])[1].get("content", "")

        breakfast_dict = {
            "Timeing": breakfast_content[1].get("description"),
            "price": price_raw
        }

    s_dict["Policy"] = {
        "checkIn": checkin_out[0].get("description") if len(checkin_out) > 0 else None,
        "checkOut": checkin_out[1].get("description") if len(checkin_out) > 1 else None,
        "frontdeskhours": checkin_out[2].get("description") if len(checkin_out) > 2 else None,
        "Breakfast": breakfast_dict
    }

    nearby_list = position_info.get("placeInfo", {}).get("wholePoiInfoList", [])
    nearby = []

    for item in nearby_list:
        nearby.append({
            "distance": item.get("distance"),
            "dist_type": item.get("distType"),
            "Name": item.get("poiName")
        })

    s_dict["Nearby_location"] = nearby

    result = []
    rooms = d.get('hotelCommentResponse', {}).get('commentStaticInfo', {}).get('roomList', [])
    picture_map = d.get('seoSSRData', {}).get('seoHotelRooms', {}).get('physicRoomMap', {})

    for room in rooms:
        room_id = room.get("id")
        if not room_id:
            continue

        room_info = {
            "id": room_id,
            "name": room.get("name"),
            "facilitys": []
        }

        room_data = picture_map.get(str(room_id), {})
        facility_list = room_data.get("baseFacilityInfo", [])
        bed_info = room_data.get("bedInfo", {})
        more_list = room_data.get("newFacilityList") or []

        for f in facility_list:
            if f.get("title"):
                room_info["facilitys"].append(f.get("title"))

        if bed_info.get("title"):
            room_info["facilitys"].append(bed_info.get("title"))

        for more in more_list:
            if more.get("title"):
                room_info["facilitys"].append(more.get("title"))

        result.append(room_info)

    s_dict["Roomdetails"] = result

    for review in comment_data.get("positiveDirection", []):
        Customer_reviews_data.append({
            "Guest_Name": review.get("userInfo", {}).get("nickName"),
            "Guest_id": review.get("id"),
            "Comment": review.get("content"),
            "Guest_Profile": review.get("userInfo", {}).get("headPictureUrl")
        })

    s_dict["Customer_reviews_data"] = Customer_reviews_data

    ratings = []
    for rate in comment_data.get("scoreDetail", []):
        ratings.append({
            "Category": rate.get("showName"),
            "Rating": rate.get("showScore")
        })

    s_dict["Ratingdata"] = ratings

    return hoteltrip.model_validate(s_dict)


def create_tables(conn):
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hotels (
        hotel_id BIGINT PRIMARY KEY,
        name VARCHAR(255),
        number_of_rooms INT,
        open_year INT,
        phone VARCHAR(20),
        description LONGTEXT,
        address VARCHAR(255),
        city VARCHAR(100),
        state VARCHAR(100),
        country VARCHAR(100),
        pincode VARCHAR(20)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hotel_policies (
        policy_id INT AUTO_INCREMENT PRIMARY KEY,
        hotel_id BIGINT UNIQUE,
        check_in_time VARCHAR(50),
        check_out_time VARCHAR(50),
        front_desk_hours VARCHAR(100),
        breakfast_time VARCHAR(100),
        breakfast_price DECIMAL(10,2),
        FOREIGN KEY (hotel_id) REFERENCES hotels(hotel_id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        room_id BIGINT PRIMARY KEY,
        hotel_id BIGINT,
        room_name VARCHAR(255),
        FOREIGN KEY (hotel_id) REFERENCES hotels(hotel_id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS room_facilities (
        facility_id INT AUTO_INCREMENT PRIMARY KEY,
        room_id BIGINT,
        facility_name VARCHAR(255),
        FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON DELETE CASCADE
    )
    """)

    conn.commit()
    cursor.close()


def insert_data(conn, hotel):
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO hotels (
            hotel_id, name, number_of_rooms, open_year,
            phone, description, address, city,
            state, country, pincode
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
            name=VALUES(name),
            number_of_rooms=VALUES(number_of_rooms),
            open_year=VALUES(open_year),
            phone=VALUES(phone),
            description=VALUES(description),
            address=VALUES(address),
            city=VALUES(city),
            state=VALUES(state),
            country=VALUES(country),
            pincode=VALUES(pincode)
    """, (
        hotel.HotelId,
        hotel.Name,
        hotel.Basic_info.get("Number_of_room"),
        hotel.Basic_info.get("OpenYear"),
        hotel.Basic_info.get("PhoneNo"),
        hotel.Basic_info.get("Description"),
        hotel.location.get("Address"),
        hotel.location.get("City"),
        hotel.location.get("State"),
        hotel.location.get("Country"),
        hotel.location.get("Pincode")
    ))

    policy = hotel.Policy or {}
    breakfast = policy.get("Breakfast", {})

    price_raw = breakfast.get("price")
    breakfast_price = None

    if price_raw:
        price_clean = ''.join(c for c in str(price_raw) if c.isdigit() or c == '.')
        breakfast_price = float(price_clean) if price_clean else None

    cursor.execute("""
        INSERT INTO hotel_policies (
            hotel_id, check_in_time, check_out_time,
            front_desk_hours, breakfast_time, breakfast_price
        )
        VALUES (%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
            check_in_time=VALUES(check_in_time),
            check_out_time=VALUES(check_out_time),
            front_desk_hours=VALUES(front_desk_hours),
            breakfast_time=VALUES(breakfast_time),
            breakfast_price=VALUES(breakfast_price)
    """, (
        hotel.HotelId,
        policy.get("checkIn"),
        policy.get("checkOut"),
        policy.get("frontdeskhours"),
        breakfast.get("Timeing"),
        breakfast_price
    ))

    for room in hotel.Roomdetails:
        cursor.execute("""
            INSERT INTO rooms (room_id, hotel_id, room_name)
            VALUES (%s,%s,%s)
            ON DUPLICATE KEY UPDATE room_name=VALUES(room_name)
        """, (room["id"], hotel.HotelId, room["name"]))

        for facility in room["facilitys"]:
            cursor.execute("""
                INSERT INTO room_facilities (room_id, facility_name)
                VALUES (%s,%s)
            """, (room["id"], facility))

    conn.commit()
    cursor.close()


file_path = r"C:\Users\vishal.mistry\Desktop\Mistry Vishal\hoteltrip\trip_hotel.json"

file_data = load_main_file(file_path)
inner_data = file_data[1]
clean_string = inner_data.replace("Jc:", "", 1)
hotel_data = json.loads(clean_string)
main_data = hotel_data[3]

hotel_model = parser(main_data)

write_file(hotel_model)

try:
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="actowiz",
        database="hoteltrip"
    )

    create_tables(conn)
    insert_data(conn, hotel_model)
    conn.close()

    print("Process completed successfully")

except Error as e:
    print("Database Error:", e)