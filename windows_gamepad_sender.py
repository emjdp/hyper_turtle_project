import socket
import json
import time

try:
    import pygame
except ImportError:
    print("pygame이 설치되어 있지 않습니다. 아래 명령어로 먼저 설치해주세요:")
    print("pip install pygame")
    exit(1)

# WSL의 IP로 보냅니다. 
# 최신 Windows 11 WSL2 (Mirrored Network) 환경이면 127.0.0.1로 통신 가능합니다.
# 만약 통신이 안된다면 WSL 터미널에서 `hostname -I`를 쳐서 나온 IP를 넣으세요.
WSL_IP = "172.22.104.144" 
UDP_PORT = 9090
SEND_HZ = 30

def main():
    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        print("Windows에 게임패드가 연결되어 있지 않습니다. 블루투스/USB 연결을 확인하세요.")
        return

    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    print(f"Windows에서 다음 컨트롤러를 인식했습니다: {joystick.get_name()}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"WSL({WSL_IP}:{UDP_PORT})로 조이스틱 데이터를 전송합니다... (종료: Ctrl+C)")
    
    clock = pygame.time.Clock()
    
    try:
        while True:
            pygame.event.pump()
            
            axes = [joystick.get_axis(i) for i in range(joystick.get_numaxes())]
            buttons = [joystick.get_button(i) for i in range(joystick.get_numbuttons())]
            
            data = {
                "axes": axes,
                "buttons": buttons
            }
            
            sock.sendto(json.dumps(data).encode('utf-8'), (WSL_IP, UDP_PORT))
            
            # 엄격한 주파수 제어 (30Hz)
            clock.tick(SEND_HZ)
            
    except KeyboardInterrupt:
        print("\n전송을 중단합니다.")
    finally:
        pygame.quit()

if __name__ == '__main__':
    main()
