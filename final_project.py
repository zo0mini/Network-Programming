#!/usr/bin/python3
'''
TFTP Client Program
Usage:
  $ tftp host_address [get|put] filename [-p port_number]
'''

import os
import sys
import socket
import argparse
from struct import pack

DEFAULT_PORT = 69  # TFTP 기본 포트
BLOCK_SIZE = 512
DEFAULT_TRANSFER_MODE = 'octet'  # 바이너리 전송 모드
TIMEOUT = 5  # 소켓 타임아웃 시간 (5초)

# Opcode 정의
OPCODE = {'RRQ': 1, 'WRQ': 2, 'DATA': 3, 'ACK': 4, 'ERROR': 5}

# 에러 코드 정의
ERROR_CODE = {
    0: "Not defined, see error message (if any).",
    1: "File not found.",
    2: "Access violation.",
    3: "Disk full or allocation exceeded.",
    4: "Illegal TFTP operation.",
    5: "Unknown transfer ID.",
    6: "File already exists.",
    7: "No such user."
}

# RRQ(읽기 요청) 또는 WRQ(쓰기 요청)를 서버에 보내는 함수
def send_request(opcode, filename, mode, server_address):
    """Send Read or Write Request (RRQ/WRQ) to the server."""
    # 요청 메시지를 생성합니다. (Opcode + 파일 이름 + 전송 모드)
    format = f'>h{len(filename)}sB{len(mode)}sB'
    request_message = pack(format, opcode, bytes(filename, 'utf-8'), 0, bytes(mode, 'utf-8'), 0)
    # 서버로 메시지를 전송합니다.
    sock.sendto(request_message, server_address)

# 데이터 블록에 대한 ACK(확인 메시지)를 서버에 보내는 함수
def send_ack(block_number, server):
    """Send ACK for a received block."""
    ack_message = pack('>hh', OPCODE['ACK'], block_number)
    sock.sendto(ack_message, server)

# 명령줄 인자를 처리하기 위한 argparse 설정
parser = argparse.ArgumentParser(description='TFTP client program')
parser.add_argument("host", help="Server IP address", type=str)
parser.add_argument("operation", help="get or put a file", type=str, choices=["get", "put"])
parser.add_argument("filename", help="Name of file to transfer", type=str)
parser.add_argument("-p", "--port", help="Server port (default: 69)", type=int, default=DEFAULT_PORT)
args = parser.parse_args()

# 서버 정보 설정
server_ip = args.host
server_port = args.port
server_address = (server_ip, server_port)

# UDP 소켓을 생성
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(TIMEOUT)  # 타임아웃 설정

# 기본 전송 모드와 사용자 입력 처리
mode = DEFAULT_TRANSFER_MODE
operation = args.operation
filename = args.filename

# 파일 다운로드(get) 작업
if operation == "get":
    # RRQ(읽기 요청)을 서버에 전송
    send_request(OPCODE['RRQ'], filename, mode, server_address)
    file = open(filename, 'wb')  # 수신한 데이터를 저장할 파일 열기
    expected_block_number = 1  # 예상되는 첫 번째 블록 번호

    while True:
        try:
            # 서버로부터 데이터 수신
            data, server_new_socket = sock.recvfrom(516)
            opcode = int.from_bytes(data[:2], 'big')  # Opcode 추출

            if opcode == OPCODE['DATA']:
                block_number = int.from_bytes(data[2:4], 'big')  # 블록 번호 추출
                if block_number == expected_block_number:
                    send_ack(block_number, server_new_socket)  # ACK 전송
                    file_block = data[4:]  # 데이터 블록 추출
                    file.write(file_block)  # 파일에 데이터 쓰기
                    expected_block_number += 1  # 다음 블록 번호 예상

                # 데이터 크기가 BLOCK_SIZE보다 작은지 확인
                if len(file_block) < BLOCK_SIZE:
                    print("File transfer completed.")
                    break

            elif opcode == OPCODE['ERROR']:
                # 에러 메시지 처리
                error_code = int.from_bytes(data[2:4], byteorder='big')
                print(f"Error: {ERROR_CODE.get(error_code, 'Unknown error')}")
                file.close()
                os.remove(filename)  # 부분적으로 받은 파일 삭제
                break

        except socket.timeout:
            # 타임아웃 발생 시 재전송 요청
            print("Timeout occurred. Retrying...")
            send_request(OPCODE['RRQ'], filename, mode, server_address)

    file.close()

# 파일 업로드(put) 작업
elif operation == "put":
    try:
        # WRQ(쓰기 요청)을 서버에 전송
        send_request(OPCODE['WRQ'], filename, mode, server_address)
        file = open(filename, 'rb')  # 전송할 파일 열기
        block_number = 0  # 블록 번호 초기화

        while True:
            # 파일에서 데이터를 읽어 데이터 블록 생성
            file_block = file.read(BLOCK_SIZE)
            block_number += 1
            data_packet = pack('>hh', OPCODE['DATA'], block_number) + file_block
            sock.sendto(data_packet, server_address)  # 데이터 패킷 전송

            try:
                # ACK 수신
                ack, _ = sock.recvfrom(4)
                ack_opcode = int.from_bytes(ack[:2], 'big')  # Opcode 추출
                ack_block_number = int.from_bytes(ack[2:4], 'big')  # 블록 번호 추출

                if ack_opcode == OPCODE['ACK'] and ack_block_number == block_number:
                    # 마지막 블록인지 확인
                    if len(file_block) < BLOCK_SIZE:
                        print("File upload completed.")
                        break

            except socket.timeout:
                # 타임아웃 발생 시 블록 재전송
                print("Timeout occurred. Resending block...")
                sock.sendto(data_packet, server_address)

    except FileNotFoundError:
        # 업로드할 파일이 없는 경우 에러 처리
        print(f"Error: File '{filename}' not found.")
    finally:
        file.close()

# 프로그램 종료
sys.exit(0)
