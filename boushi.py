import streamlit as st
import requests
import math
import json
import wave
import time


# latitude, longitudeを返す関数
def get_current_location(api_key):
    # Geolocation APIを使用して現在の緯度と経度を取得
    geolocation_url = f"https://www.googleapis.com/geolocation/v1/geolocate?key={api_key}"
    response = requests.post(geolocation_url)
    location_data = response.json()
    latitude = location_data["location"]["lat"]
    longitude = location_data["location"]["lng"]

    print(f"current location: ({latitude}, {longitude})")

    return (latitude, longitude)


def get_routes(api_key, departure, destination):
    print("debbug: getting rotues ...")
    # Google Directions APIを使用して到着時間を取得
    directions_url = f"https://maps.googleapis.com/maps/api/directions/json?origin={departure}&destination={destination}&mode=walking&key={api_key}&language=ja"
    response = requests.get(directions_url)
    print("debbug: got rotues")
    directions_data = response.json()
    status = directions_data["status"]
    if status != "OK":
        return False
    else:
        # 最初の経路を取得
        steps = directions_data["routes"][0]["legs"][0]["steps"]

        # 曲がり角を取得
        rs = []
        l = len(steps)
        for i in range(l):
            step = steps[i]
            end = [step["end_location"]["lat"], step["end_location"]["lng"]]
            instruction = step["html_instructions"]
            dst = step["distance"]["value"]
            rs.append([instruction, dst, end])
        rs.append(["goal", [steps[l - 1]["end_location"]["lat"], steps[l - 1]["end_location"]["lng"]]])
        return rs


def calc_distance(loc1, loc2):
    lat1 = loc1[0]
    lng1 = loc1[1]
    lat2 = loc2[0]
    lng2 = loc2[1]
    # 緯度・経度をラジアンに変換
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])

    # Haversine formula
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # 地球の半径 (単位: メートル)
    radius_of_earth = 6371000.0

    # 2点間の距離を計算
    distance = radius_of_earth * c

    return distance


def interpret(str):
    words = []
    piv = 0
    while piv < len(str):
        if str[piv] == "<":
            if str[piv + 1 : piv + 4] == "div":
                break
            while str[piv] != ">":
                piv += 1
            piv += 1
        elif str[piv] != " ":
            word = ""
            while str[piv] != " " and str[piv] != "<":
                word += str[piv]
                piv += 1
                if piv == len(str):
                    break
            words.append(word)
        else:
            piv += 1

    if "右" in words:
        flag = 1
    elif "右折" in words:
        flag = 1
    elif "左" in words:
        flag = 2
    elif "左折" in words:
        flag = 2
    else:
        flag = 0
    sentence = ""
    for i in words:
        if i == "/":
            sentence += "、"
        else:
            sentence += i
    sentence += "のだ。"
    return [sentence, flag]


def make_zunda_read(text):
    # エンジン起動時に表示されているIP、portを指定
    # ここ調整する必要あるかも
    host = "127.0.0.1"
    port = 50021

    # 音声化する文言と話者を指定(3で標準ずんだもんになる)
    params = (
        ("text", text),
        ("speaker", 3),
    )

    # 音声合成用のクエリ作成
    query = requests.post(f"http://{host}:{port}/audio_query", params=params)

    # 音声合成を実施
    synthesis = requests.post(
        f"http://{host}:{port}/synthesis",
        headers={"Content-Type": "application/json"},
        params=params,
        data=json.dumps(query.json()),
    )

    return synthesis.content


def zunda_into_wav(voice):
    with wave.open("zunda.wav", "wb") as wav_file:
        # フォーマット設定
        wav_file.setnchannels(1)  # モノラル
        wav_file.setsampwidth(2)  # サンプルサイズ（バイト数）を2に設定
        wav_file.setframerate(24000)  # サンプリングレートを設定
        wav_file.writeframes(voice)


def send_to_ESP(flag, ip):
    try:
        print("debug: sending...")
        # Step 1: int型の変数をサーバに送信
        data = str(flag)
        response = requests.post(f"http://{ip}/direction", data=data)

        # サーバからのレスポンスを表示
        print(response.text)
        print("/")

        # サーバが"Direction received"を返した場合のみファイルを送信
        if response.text == "Direction received":
            with open("zunda.wav", "rb") as file:
                files = {"file": file}
                response = requests.post(f"http://{ip}/upload", files=files)

                # サーバからのレスポンスを表示
                print(f"{response.text}")
                print("/")
                print("debug:response received")
            print("debug: wav sent")
            return
    except Exception as e:
        print(f"エラー: {e}")


def time_announce(dst):
    time = dst / 80  # 徒歩1分は秒速80m
    if time < 1:
        return "1分以内に到着するのだ。"
    else:
        return f"およそ{int(time)}分かかるのだ。"


def search_nearby_places(api_key, latitude, longitude, radius=15):
    # Places APIを使用して指定された座標の周辺施設を検索
    places_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={latitude},{longitude}&radius={radius}&key={api_key}&language=ja"
    response = requests.get(places_url)
    places_data = response.json()

    if "results" in places_data and len(places_data["results"]) > 0:
        ls = []
        for place in places_data["results"]:
            ls.append([len(place["name"]), place["name"]])
        if len(ls) > 2:
            ls.sort()
            ls.pop(0)
            ls.pop(0)
            text = ""
            if len(ls) > 3:
                l = 3
            else:
                l = len(ls)
            for i in range(l):
                text += ls[i][1]
                text += "、"
            return f"その後、{text}のあたりまで行くのだ。"
        else:
            return False
    else:
        return False


def gen_voice(points, cur, l, api_key, ip):
    if cur < l - 1:
        interpreted = interpret(points[cur][0])
        text = interpreted[0]
        flag = interpreted[1]
        # 1つ後の地点との距離を計算し、文章化
        print("here", points[cur])
        dst = points[cur][1]
        end = points[cur][2]
        if cur == l - 2:
            # 次が最後の地点なら終わり
            text += f"その後、{dst}メートル進むと、目的地に到着するのだ。{time_announce(dst)}"
        else:
            place = search_nearby_places(api_key, end[0], end[1])
            if place == False or dst < 20:
                text += f"その後、{dst}メートル進むのだ。"
            else:
                text += f"{place}"
    else:
        text = "目的地に到着したのだ。"
        flag = 0

    print(f"debbug: {text}")

    voice = make_zunda_read(text)
    zunda_into_wav(voice)
    send_to_ESP(flag, ip)


def wait_for_server_message(ip):
    try:
        print("debbug: waiting for server message ...")
        response = requests.get(f"http://{ip}/pinstate")
        print(f"debbug: server response : {response}")
        if response.text == "1":
            print("received")
            return True
        else:
            print("Unexpected response")
            time.sleep(5)
            return False
    except Exception as e:
        print(f"エラー: {e}")


def wander(points, api_key, ip):
    print("debbug: navigating start")
    l = len(points)

    # 最初の指示
    gen_voice(points, 0, l, api_key, ip)
    cur = 1

    # ボタンが押されるたびにgen_voice
    while cur < l:
        tmp = False
        while not tmp:
            tmp = wait_for_server_message(ip)
        # if not tmp:
        #     # エラー処理、多分いらない
        #     zunda_into_wav(make_zunda_read("予期せぬエラーが発生したのだ。案内を終了するのだ。"))
        #     send_to_ESP(0, ip)
        #     break
        gen_voice(points, cur, l, api_key, ip)
        cur += 1
    return


def main():
    st.title("歩きスマホぼうし")

    if "google_maps_api_key" not in st.session_state or "ip_address" not in st.session_state:
        st.session_state["google_maps_api_key"] = st.secrets.get("google_maps_api_key", "")
        st.session_state["ip_address"] = st.secrets.get("ip_address", "")

    with st.sidebar:
        google_maps_api_key = st.text_input(
            "Google Maps APIキーを入力してください:", value=st.session_state["google_maps_api_key"], type="password"
        )
        ip_address = st.text_input("IPアドレスを入力してください:", value=st.session_state["ip_address"])

    if st.sidebar.button("設定を保存"):
        st.session_state["google_maps_api_key"] = google_maps_api_key
        st.session_state["ip_address"] = ip_address

        # st.session_state["google_maps_api_key"]
        #  st.session_state["ip_address"]

    # 目的地の検索
    departure = st.text_input("現在地を入力してください:", value="目白台インターナショナルビレッジ")
    destination = st.text_input("目的地を入力してください:", value="目白御殿")

    if st.button("検索"):
        with st.spinner("実行中です..."):
            try:
                # ここが関数いじること
                points = get_routes(st.session_state["google_maps_api_key"], departure, destination)
                print("取得した経路", points)
                if not points:
                    st.error(f"{destination}への経路が検索できませんでした。")
                else:
                    st.success(f"{departure}から{destination}への経路を検索できました。案内を開始します。")
                    wander(points, st.session_state["google_maps_api_key"], st.session_state["ip_address"])
                    st.success(f"{destination}に到着しました。案内を終了します。")
            except ValueError as e:
                st.error(str(e))


if __name__ == "__main__":
    main()
