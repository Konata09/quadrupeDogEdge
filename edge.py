import base64
import copy
import json
import threading
import time
import paho.mqtt.client as mqtt
import logging

response_json = {
    "dog_id": 0,
    "timestamp": 1600000000,
    "return_code": 0,
    "return_msg": "OK",
    "type": "ControlData",
    "data": dict
}

control_data = {
    "control_mode": 11,
    "gait_type": None,
    "v_des": [0.0, 0.0, 0.0],  # 前进 横移 自转 -1~1
    "step_height": 0.0,
    "rpy_des": [0.0, 0.0, 0.0]
}

gesture_map = {
    0: "Unknown",  # 未识别
    1: "Forward",  # 前进
    2: "Back",  # 后退
    3: "Stand",  # 站立
    4: "Down"  # 趴下
}

DOCKER_HOSTNAME = 'DOCKER_HOSTNAME'
sub_topic = "robot_upload"
pub_topic = "control"
broker = "172.31.120.1"
qos = 0
reset_delay = 4
robot_timer = {}

logging.basicConfig(format='[%(levelname)8s] %(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S', level=logging.DEBUG)


def on_connect(client, userdata, flags, rc):
    logging.info('Connected to MQTT broker with result code ' + str(rc))
    client.subscribe(sub_topic)


def on_message(client, userdata, msg):
    message = msg.payload.decode("utf-8")
    logging.debug(f'Received MQTT Message:')
    logging.debug(f'\ttopic: {msg.topic}')
    logging.debug(f'\tmessage: {message}')

    if msg.topic == sub_topic:
        handle_mqtt_msg(client, message)


def subscript_mqtt():
    client = mqtt.Client(client_id=DOCKER_HOSTNAME, clean_session=False, transport='tcp')
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(host=broker, port=1883, keepalive=30)

    client.loop_forever()


def handle_mqtt_msg(client, message):
    json_msg = json.loads(message)
    msg_type = json_msg['type']
    if msg_type == 'getControlByCam':
        robot_id = json_msg['dog_id']
        robot_name = json_msg['dog_name']
        sent_time = json_msg['timestamp']
        img = base64.b64decode(json_msg['data']['image'])
        logging.info(f'handle {msg_type}')
        logging.info(f'\trobot id: {robot_id}')
        logging.info(f'\trobot name: {robot_name}')
        logging.debug(f'\timg: {img}')
        gesture = call_recognition(img)
        logging.info(f'\tgot gesture: {gesture_map[gesture]}')
        spend_time = int(time.time()) - sent_time
        logging.info(f'\tspend time: {spend_time}')
        if gesture == 0:

            return
        ctrl_data = gesture_to_ctrl_data(robot_id, gesture)
        publish_mqtt(client, pub_topic, json.dumps(ctrl_data))
        if robot_timer.get(robot_id) is not None:
            robot_timer[robot_id] = reset_delay
            return
        else:
            robot_timer[robot_id] = reset_delay
            threading.Thread(target=reset_robot, args=(client, robot_id))


t = 1
def call_recognition(img_byte):
    time.sleep(1)
    global t
    if t == 1:
        t = 0
        return 1
    else:
        return 0


def publish_mqtt(client, topic, payload):
    logging.info(f'Publish MQTT Message:')
    logging.info(f'\ttopic: {topic}')
    logging.info(f'message: {payload}')
    client.publish(topic=topic, payload=payload, qos=qos)


def gesture_to_ctrl_data(robot_id, gesture):
    resp = copy.deepcopy(response_json)
    resp['timestamp'] = int(time.time())
    resp['dog_id'] = robot_id
    resp['data'] = gesture_switch_map[gesture]()
    return resp


def Forward():
    resp_data = copy.deepcopy(control_data)
    resp_data['v_des'] = [0.6, 0.0, 0.0]
    resp_data['step_height'] = 0.1
    return resp_data


def Back():
    resp_data = copy.deepcopy(control_data)
    resp_data['v_des'] = [-0.6, 0.0, 0.0]
    resp_data['step_height'] = 0.1
    return resp_data


def Stand():
    resp_data = copy.deepcopy(control_data)
    resp_data['step_height'] = 0.1
    return resp_data


def Down():
    resp_data = copy.deepcopy(control_data)
    resp_data['step_height'] = 0.04
    return resp_data


gesture_switch_map = {
    1: Forward,  # 前进
    2: Back,  # 后退
    3: Stand,  # 站立
    4: Down  # 趴下
}


def reset_robot(client, robot_id):
    global timer
    while 1:
        time.sleep(1)
        timer = timer - 1
        if timer <= 0:
            logging.info(f'RESET: robot_id: {robot_id}')
            resp = copy.deepcopy(response_json)
            resp['timestamp'] = int(time.time())
            resp['dog_id'] = robot_id
            resp['data'] = Stand()
            publish_mqtt(client, pub_topic, json.dumps(resp))


if __name__ == '__main__':
    subscript_mqtt()
