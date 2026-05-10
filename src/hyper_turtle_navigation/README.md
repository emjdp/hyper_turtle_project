# hyper_turtle_navigation

This package is a placeholder for future autonomous navigation capabilities.

## 2차 작업: Nav2 기반 자율 주행

초기 수동 매핑(SLAM) 이후, 저장된 맵 기반의 Nav2 waypoint navigation을 구현할 예정입니다.

현재 계획된 파이프라인:
1. `hyper_turtle_mapping`을 사용해 생성한 맵(`maps/<map_name>.yaml`, `maps/<map_name>.pgm`)을 Nav2 `map_server`에 로드
2. AMCL 또는 다른 Nav2 localization을 통한 초기 위치 추정
3. `nav2_simple_commander` 또는 Waypoint Follower 기능을 활용한 자율 순찰
4. 순찰 중 RGB-D 카메라 데이터 및 라이다/오도메트리 데이터를 저장하거나 실시간 처리하여 그래피티 탐지에 활용

본 패키지의 구성 요소는 하드웨어 테스트 및 매핑이 완료된 이후 2차 개발 단계에서 추가될 것입니다.
