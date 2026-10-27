import time
import unittest
import launch
import launch_testing
import launch_testing.actions
import launch_testing.markers
import launch_testing.asserts
import pytest
import rclpy
import rclpy.node

from sensor_msgs.msg import Image
from ffmpeg_image_transport_msgs.msg import FFMPEGPacket
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode
from depthai_ros_driver_v3.test_helper import TestHelper


@pytest.mark.rostest
def generate_test_description():
    name = "oak"
    params = {
        "rgb": {
            "i_synced": True,
            "i_low_bandwidth": True,
            "i_publish_compressed": True,
            "i_low_bandwidth_profile": 2,
        },
        "stereo": {"i_synced": True},
    }

    driver = ComposableNodeContainer(
        name=f"{name}_container",
        namespace="",
        package="rclcpp_components",
        executable="component_container",
        composable_node_descriptions=[
            ComposableNode(
                package="depthai_ros_driver_v3",
                plugin="depthai_ros_driver::Driver",
                name=name,
                parameters=[
                    params,
                ],
            )
        ],
        output="both",
    )

    return launch.LaunchDescription(
        [
            driver,
            launch.actions.TimerAction(
                period=1.0, actions=[launch_testing.actions.ReadyToTest()]
            ),
        ]
    ), {"driver_node": driver}


class TestDriverLaunch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def setUp(self):
        self.node = rclpy.create_node("test")
        self.testHelper = TestHelper(self.node)

    def tearDown(self):
        self.node.destroy_node()

    def test_driver_output(self, proc_output):
        proc_output.assertWaitFor("Driver ready!", timeout=10.0, stream="stderr")

    def test_synced_stamps(self, proc_output):
        rgbStamps = set()
        depthStamps = set()
        self.node.create_subscription(
            FFMPEGPacket,
            "/oak/rgb/image_raw/compressed",
            lambda msg: rgbStamps.add((msg.header.stamp.sec, msg.header.stamp.nanosec)),
            10,
        )
        self.node.create_subscription(
            Image,
            "/oak/stereo/image_raw",
            lambda msg: depthStamps.add((msg.header.stamp.sec, msg.header.stamp.nanosec)),
            10,
        )
        end_time = time.time() + 5
        while time.time() < end_time and len(rgbStamps & depthStamps) <= 30:
            rclpy.spin_once(self.node, timeout_sec=1)
        self.assertGreater(len(rgbStamps & depthStamps), 30)


@launch_testing.post_shutdown_test()
class TestShutdown(unittest.TestCase):
    def test_exit_codes(self, proc_info):
        launch_testing.asserts.assertExitCodes(proc_info)
