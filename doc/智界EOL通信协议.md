# 智界EOL通信协议

> 从 `doc/智界EOL通信协议.xlsx` 转换生成。

## 协议格式

|  | ID | Byte0 | Byte1 | Byte2 | Byte3 | Byte4 | Byte5 | Byte6 | Byte7 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 上位机发送 | 7F0 | 0x10 | DeviceID | DeviceOperation | / | / | / | / | / |
| BMS回复 | 7F8 | 0x11 | DeviceID | DeviceOperation | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | / | / | / | / |

## 0x03(绝缘)

|  | ID | Byte0 | Byte1 | Byte2 | Byte3 | Byte4 | Byte5 | Byte6 | Byte7 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 发送 | 0x7F0 | 0x10 | 0x03 | 0x01 | / | 0x01 | 0:P/N均断开<br>1:P闭合 N断开<br>2:P断开 N闭合 | / | / | 控制绝缘桥臂 |
| 回复 | 0x7F8 | 0x11 | 0x03 | 0x01 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | / | / | / | / |  |
| 发送 | 0x7F0 | 0x10 | 0x03 | 0x03 | / | / | / | / | / | 绝缘值,factor:0.001 |
| 回复 | 0x7F8 | 0x11 | 0x03 | 0x03 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit23:bit16 | bit15:bit8 | bit7:bit0 | 0:正<br>1:负 |  |

## 0x04(GPIO)

|  | ID | Byte0 | Byte1 | Byte2 | Byte3 | Byte4 | Byte5 | Byte6 | Byte7 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 发送 | 0x7F0 | 0x10 | 0x04 | 0x01 | / | GPIO索引 | / | / | / | 读取GPIO状态 |
| 回复 | 0x7F8 | 0x11 | 0x04 | 0x01 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | GPIO索引 | 电平状态 | / | / |  |
| 发送 | 0x7F0 | 0x10 | 0x04 | 0x05 | / | GPIO索引 | 电平状态 | / | / | 写入GPIO状态 |
| 回复 | 0x7F8 | 0x11 | 0x04 | 0x05 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | GPIO索引 | / | / | / |  |
| GPIO索引 | GPIO Mapping |  |  |  |  |  |  |  |  |  |
| 0x01 | DIO_CHANNEL_HSD_O_00_EN |  |  |  |  |  |  |  |  |  |
| 0x02 | DIO_CHANNEL_HSD_O_01_EN |  |  |  |  |  |  |  |  |  |
| 0x03 | DIO_CHANNEL_HSD_O_02_EN |  |  |  |  |  |  |  |  |  |
| 0x04 | DIO_CHANNEL_HSD_O_03_EN |  |  |  |  |  |  |  |  |  |
| 0x05 | DIO_CHANNEL_HSD_O_04_EN |  |  |  |  |  |  |  |  |  |
| 0x06 | DIO_CHANNEL_HSD_O_05_EN |  |  |  |  |  |  |  |  |  |
| 0x07 | DIO_CHANNEL_HSD_O_06_EN |  |  |  |  |  |  |  |  |  |
| 0x08 | DIO_CHANNEL_HSD_O_07_EN |  |  |  |  |  |  |  |  |  |
| 0x09 | DIO_CHANNEL_LSD_O_00_EN |  |  |  |  |  |  |  |  |  |
| 0x0A | DIO_CHANNEL_LSD_O_01_EN |  |  |  |  |  |  |  |  |  |
| 0x0B | DIO_CHANNEL_LSD_O_02_EN |  |  |  |  |  |  |  |  |  |
| 0x0C | DIO_CHANNEL_LSD_O_03_EN |  |  |  |  |  |  |  |  |  |
| 0x0D | DIO_CHANNEL_LSD_O_04_EN |  |  |  |  |  |  |  |  |  |
| 0x0E | DIO_CHANNEL_LSD_O_05_EN |  |  |  |  |  |  |  |  |  |
| 0x10 | CC1_2015+_S2 |  |  | 新增 |  |  |  |  |  |  |
| 0x11 | CC2_SW3 |  |  |  |  |  |  |  |  |  |
| 0x12 | LINK |  |  |  |  |  |  |  |  |  |
| 0x13 | FAS |  |  |  |  |  |  |  |  |  |
| 0x14 | SC_EN1 |  |  |  |  |  |  |  |  |  |

## 0x05(PWM)

|  | ID | Byte0 | Byte1 | Byte2 | Byte3 | Byte4 | Byte5 | Byte6 | Byte7 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 发送 | 0x7F0 | 0x10 | 0x05 | 0x01 | / | pwm通道 | / | / | / | 读取pwm占空比 |
| 回复 | 0x7F8 | 0x11 | 0x05 | 0x01 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | 占空比 | / | / | / |  |
| 发送 | 0x7F0 | 0x10 | 0x05 | 0x02 | / | pwm通道 | / | / | / | 读取pwm频率 |
| 回复 | 0x7F8 | 0x11 | 0x05 | 0x02 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 |  |

## 0x06(ADC)

|  | ID | Byte0 | Byte1 | Byte2 | Byte3 | Byte4 | Byte5 | Byte6 | Byte7 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 发送 | 0x7F0 | 0x10 | 0x06 | 0x01 | / | ADC索引 | / | / | / | 读取ADC原始值 |
| 回复 | 0x7F8 | 0x11 | 0x06 | 0x01 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | ADC索引 | bit15:bit8 | bit7:bit0 | / |  |
| 发送 | 0x7F0 | 0x10 | 0x06 | 0x02 | / | ADC索引 | / | / | / | 读取ADC转化值<br>factor:0.001 |
| 回复 | 0x7F8 | 0x11 | 0x06 | 0x02 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | ADC索引 | bit15:bit8 | bit7:bit0 | / |  |
| ADC索引 | 通道 |  |  |  |  |  |  |  |  |  |
| 0 | KL30_IN1_V_A2D |  |  |  |  |  |  |  |  |  |
| 1 | WKD_EXT1_ADC |  |  |  |  |  |  |  |  |  |
| 2 | WKD_EXT2_ADC |  |  |  |  |  |  |  |  |  |
| 3 | WKD_INT1_INT2_A2D |  |  |  |  |  |  |  |  |  |
| 4 | WKD_INT3_INT4_A2D |  |  |  |  |  |  |  |  |  |
| 5 | WKD_EXT3_ADC |  |  |  |  |  |  |  |  |  |
| 6 | KL30_IN2_V_A2D |  |  |  |  |  |  |  |  |  |
| 7 | WKD_EXT6_ADC |  |  |  |  |  |  |  |  |  |
| 8 | HWREV_A2D |  |  |  |  |  |  |  |  |  |
| 9 | HSD_O_00_USNS |  |  |  |  |  |  |  |  |  |
| 10 | HSD_O_01_USNS |  |  |  |  |  |  |  |  |  |
| 11 | HSD_O_02_USNS |  |  |  |  |  |  |  |  |  |
| 12 | HSD_O_03_USNS |  |  |  |  |  |  |  |  |  |
| 13 | WKD_INT6_ADC |  |  |  |  |  |  |  |  |  |
| 14 | GB2015_CC2_PE |  |  |  |  |  |  |  |  |  |
| 15 | HSD_O_06_USNS |  |  |  |  |  |  |  |  |  |
| 16 | HSD_O_07_USNS |  |  |  |  |  |  |  |  |  |
| 17 | HSD_I_CS1_4 |  |  |  |  |  |  |  |  |  |
| 18 | LSD_V_AD1 |  |  |  |  |  |  |  |  |  |
| 19 | LSD_V_AD2 |  |  |  |  |  |  |  |  |  |
| 20 | NTCF_MCU |  |  |  |  |  |  |  |  |  |
| 21 | HSD_I_CS7_8 |  |  |  |  |  |  |  |  |  |
| 22 | SIG1_A_ADC |  |  |  |  |  |  |  |  |  |
| 23 | HALL_IN1_ADC |  |  |  |  |  |  |  |  |  |
| 24 | SIG3_A_ADC |  |  |  |  |  |  |  |  |  |
| 25 | LSD_V_AD3 |  |  |  |  |  |  |  |  |  |
| 26 | SBC_VS1 |  |  |  |  |  |  |  |  |  |
| 27 | HSD_O_04_USNS |  |  |  |  |  |  |  |  |  |
| 28 | LSD_V_AD4 |  |  |  |  |  |  |  |  |  |
| 29 | HSD_O_05_USNS |  |  |  |  |  |  |  |  |  |
| 30 | NTCF_I_00 |  |  |  |  |  |  |  |  |  |
| 31 | NTCF_I_01 |  |  |  |  |  |  |  |  |  |
| 32 | INPUT2_USNS |  |  |  |  |  |  |  |  |  |
| 33 | INPUT3_USNS |  |  |  |  |  |  |  |  |  |
| 34 | HALL_5V_ADC |  |  |  |  |  |  |  |  |  |
| 35 | WKD_INT7_ADC |  |  |  |  |  |  |  |  |  |
| 36 | NTCF_I_02 |  |  |  |  |  |  |  |  |  |
| 37 | NTCF_I_03 |  |  |  |  |  |  |  |  |  |
| 38 | NTCF_I_04 |  |  |  |  |  |  |  |  |  |
| 39 | HSD_I_CS5_6 |  |  |  |  |  |  |  |  |  |
| 40 | NTCF_I_05 |  |  |  |  |  |  |  |  |  |
| 41 | CHRG_GB2015_CC1 |  |  |  |  |  |  |  |  |  |
| 42 | CHRG_GB_CC2 |  |  |  |  |  |  |  |  |  |
| 43 | INPUT1_USNS |  |  |  |  |  |  |  |  |  |
| 44 | OUTPUT3_USNS |  |  |  |  |  |  |  |  |  |
| 45 | WKD_EXT4_ADC |  |  |  |  |  |  |  |  |  |
| 46 | Pulse1_ADC |  |  |  |  |  |  |  |  |  |
| 47 | OUTPUT2_USNS |  |  |  |  |  |  |  |  |  |
| 48 | OUTPUT1_USNS |  |  |  |  |  |  |  |  |  |

## 0x07(CSC)

|  | ID | Byte0 | Byte1 | Byte2 | Byte3 | Byte4 | Byte5 | Byte6 | Byte7 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 发送 | 0x7F0 | 0x10 | 0x07 | 0x01 | / | 节点数目 | / | / | / | 设置节点数目（支持1~12) |
| 回复 | 0x7F8 | 0x11 | 0x07 | 0x01 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | / | / | / | / |  |
| 发送 | 0x7F0 | 0x10 | 0x07 | 0x02 | / | 高压索引<br>0x02:HV1<br>0x03:HV2<br>0x03:HV3<br>0x0B:link1<br>0x0C:link2 | / | / | / | 读取高压 |
| 回复 | 0x7F8 | 0x11 | 0x07 | 0x02 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 |  |
| 发送 | 0x7F0 | 0x10 | 0x07 | 0x05 | / | / | 0:关闭均衡<br>非0：开启均衡 | / | / | 均衡控制（智界项目具有休眠均衡功能，若休眠不需开均衡，休眠前关闭均衡） |
| 回复 | 0x7F8 | 0x11 | 0x07 | 0x05 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | / | / | / | / |  |
| 发送 | 0x7F0 | 0x10 | 0x07 | 0x0E | / | 电芯索引<br>bit15:bit8 | 电芯索引<br>bit7:bit0 | / | / | 读取单体电压<br>factor:0.001 |
| 回复 | 0x7F8 | 0x11 | 0x07 | 0x0E | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 |  |
| ` | 0x7F0 | 0x10 | 0x07 | 0x0F | / | stack索引<br>bit15:bit8 | stack索引<br>bit7:bit0 | / | / | 读取stack电压<br>factor:0.001 |
| 回复 | 0x7F8 | 0x11 | 0x07 | 0x0F | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 |  |
| 发送 | 0x7F0 | 0x10 | 0x07 | 0x10 | / | / | / | / | / | 读取快充阻抗 |
| 回复 | 0x7F8 | 0x11 | 0x07 | 0x10 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 |  |

## 0x08(CRASH)

|  | ID | Byte0 | Byte1 | Byte2 | Byte3 | Byte4 | Byte5 | Byte6 | Byte7 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 发送 | 0x7F0 | 0x10 | 0x08 | 0x01 | / | / | / | / | / | 读取pwm占空比 |
| 回复 | 0x7F8 | 0x11 | 0x08 | 0x01 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | 占空比 | / | / | / |  |
| 发送 | 0x7F0 | 0x10 | 0x08 | 0x02 | / | / | / | / | / | 读取pwm频率 |
| 回复 | 0x7F8 | 0x11 | 0x08 | 0x02 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 |  |
| 发送 | 0x7F0 | 0x10 | 0x08 | 0x03 | / | 索引：<br>0:sig1<br>1:sig3 | / | / | / | 读取脉冲阻抗 |
| 回复 | 0x7F8 | 0x11 | 0x08 | 0x03 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 |  |
| 发送 | 0x7F0 | 0x10 | 0x08 | 0x04 | / | / | / | / | / | 读取脉冲宽度 |
| 回复 | 0x7F8 | 0x11 | 0x08 | 0x04 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 |  |

## 0x09(RTC)

|  | ID | Byte0 | Byte1 | Byte2 | Byte3 | Byte4 | Byte5 | Byte6 | Byte7 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 发送 | 0x7F0 | 0x10 | 0x09 | 0x04 | / | / | / | / | / | 读取RTC时间 |
| 回复 | 0x7F8 | 0x11 | 0x09 | 0x04 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 |  |
| 发送 | 0x7F0 | 0x10 | 0x09 | 0x05 | / | 0x02 | bit23:bit16 | bit15:bit8 | bit7:bit0 | 设置RTC唤醒时间 |
| 回复 | 0x7F8 | 0x11 | 0x09 | 0x05 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | / | / | / | / |  |
| 发送 | 0x7F0 | 0x10 | 0x09 | 0x07 | / | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 | 设置RTC时间 |
| 回复 | 0x7F8 | 0x11 | 0x09 | 0x07 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | / | / | / | / |  |

## 0x10(NTC)

|  | ID | Byte0 | Byte1 | Byte2 | Byte3 | Byte4 | Byte5 | Byte6 | Byte7 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 发送 | 0x7F0 | 0x10 | 0x10 | 0x01 | / | 温感索引 | / | / | / | 读取单体温感,<br>offset:-50 |
| 回复 | 0x7F8 | 0x11 | 0x10 | 0x01 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 |  |
| 发送 | 0x7F0 | 0x10 | 0x10 | 0x02 | / | 温感索引 | / | / | / | 读取PCB温感<br>offset:-50 |
| 回复 | 0x7F8 | 0x11 | 0x10 | 0x02 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 |  |
| 发送 | 0x7F0 | 0x10 | 0x10 | 0x04 | / | 温感索引 | / | / | / | 读取主机温感<br>offset:-50 |
| 回复 | 0x7F8 | 0x11 | 0x10 | 0x04 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 |  |
| 发送 | 0x7F0 | 0x10 | 0x10 | 0x05 | / | 温感索引 | / | / | / | 读取主机PCB温感<br>offset:-50 |
| 回复 | 0x7F8 | 0x11 | 0x10 | 0x05 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 |  |

## 0x0A(EEPROM)

|  | ID | Byte0 | Byte1 | Byte2 | Byte3 | Byte4 | Byte5 | Byte6 | Byte7 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 发送 | 0x7F0 | 0x10 | 0x0A | 0x01 | / | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 | 设置EEPROM操作地址 |
| 回复 | 0x7F8 | 0x11 | 0x0A | 0x01 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | / | / | / | / |  |
| 发送 | 0x7F0 | 0x10 | 0x0A | 0x03 | / | / | / | / | / | 读取EEPROM数据，每次读四字节，读完之后操作地址自动加4 |
| 回复 | 0x7F8 | 0x11 | 0x0A | 0x03 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | byte(地址0） | byte(地址1） | byte(地址2） | byte(地址3） |  |
| 发送 | 0x7F0 | 0x10 | 0x0A | 0x05 | / | byte(地址0） | byte(地址1） | byte(地址2） | byte(地址3） | 写入EEPROM数据，每次写四字节，写完之后操作地址自动加4 |
| 回复 | 0x7F8 | 0x11 | 0x0A | 0x05 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | / | / | / | / |  |

## 0x0B(电流)

|  | ID | Byte0 | Byte1 | Byte2 | Byte3 | Byte4 | Byte5 | Byte6 | Byte7 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 发送 | 0x7F0 | 0x10 | 0x0B | 0x01 | / | / | / | / | / | 读取霍尔电流<br>offset:-800<br>factor:0.001 |
| 回复 | 0x7F8 | 0x11 | 0x0B | 0x01 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 |  |
| 发送 | 0x7F0 | 0x10 | 0x0B | 0x03 | / | / | / | / | / | 读取霍尔电流<br>offset:-800<br>factor:0.001 |
| 回复 | 0x7F8 | 0x11 | 0x0B | 0x03 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 |  |

## 0xFF

|  | ID | Byte0 | Byte1 | Byte2 | Byte3 | Byte4 | Byte5 | Byte6 | Byte7 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 发送 | 0x7F0 | 0x10 | 0xFF | 0x06 | / | / | / | / | / | 读取第一唤醒源 |
| 回复 | 0x7F8 | 0x11 | 0xFF | 0x06 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | 第一唤醒源 | / | / | / |  |
| 发送 | 0x7F0 | 0x10 | 0xFF | 0x0E | / | / | / | / | / | 读压力传感器 |
| 回复 | 0x7F8 | 0x11 | 0xFF | 0x0E | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit31:bit24 | bit23:bit16 | bit15:bit8 | bit7:bit0 |  |
| 发送 | 0x7F0 | 0x10 | 0xFF | 0x11 | / | / | / | / | / | 读取高边负载回采电压 |
| 回复 | 0x7F8 | 0x11 | 0xFF | 0x11 | ResponseCode:<br>0x40:肯定响应<br>0x80:否定响应 | bit15:bit8 | bit7:bit0 | / | / |  |
| 唤醒源 |  |  |  |  |  |  |  |  |  |  |
| WAKE_MASK_KL15 |  | 0x1 |  |  |  |  |  |  |  |  |
| WAKE_MASK_CAN |  | 0x2 |  |  |  |  |  |  |  |  |
| WAKE_MASK_EXT3 |  | 0x4 |  |  |  |  |  |  |  |  |
| WAKE_MASK_AUX |  | 0x8 |  |  |  |  |  |  |  |  |
| WAKE_MASK_RTC |  | 0x10 |  |  |  |  |  |  |  |  |
| WAKE_MASK_TPL |  | 0x20 |  |  |  |  |  |  |  |  |
| WAKE_MASK_BPS_RSV |  | 0x40 |  |  |  |  |  |  |  |  |
| WAKE_MASK_EXT4 |  | 0x80 |  |  |  |  |  |  |  |  |
| WAKE_MASK_EXT6 |  | 0x100 |  |  |  |  |  |  |  |  |
| WAKE_MASK_CAN2 |  | 0x200 |  |  |  |  |  |  |  |  |
| WAKE_MASK_CAN3 |  | 0x400 |  |  |  |  |  |  |  |  |
