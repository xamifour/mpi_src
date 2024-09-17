# usermanager/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
import json

class TrafficUsageConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = None
        await self.accept()

    async def receive(self, text_data):
        data = json.loads(text_data)
        self.session_id = data.get('session_id')

        if self.session_id:
            # Add the user to a group identified by their session_id
            await self.channel_layer.group_add(
                f'session_{self.session_id}',
                self.channel_name
            )

    async def disconnect(self, close_code):
        if self.session_id:
            await self.channel_layer.group_discard(
                f'session_{self.session_id}',
                self.channel_name
            )

    # This method handles the traffic updates sent by the task
    async def send_traffic_update(self, event):
        traffic_data = event['traffic_data']
        await self.send(text_data=json.dumps(traffic_data))
