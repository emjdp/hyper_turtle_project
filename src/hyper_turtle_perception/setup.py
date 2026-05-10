from setuptools import find_packages, setup

package_name = 'hyper_turtle_perception'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='emjdp',
    maintainer_email='emjdp@example.com',
    description='Perception placeholder for graffiti detection',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'placeholder_node = hyper_turtle_perception.placeholder_node:main'
        ],
    },
)
