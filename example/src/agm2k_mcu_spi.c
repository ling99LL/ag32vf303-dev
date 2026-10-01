#include "example.h"

#if 1

typedef union
{
  uint32_t Val;
  uint8_t v[4];
  uint16_t w[2];
  struct
  {
    uint8_t LB;
    uint8_t HB;
    uint8_t UB;
    uint8_t MB;
  }byte;
}UINT32_VAL;

typedef union
{
  uint16_t Val;
  struct
  {
    uint8_t LB;
    uint8_t HB;
  }byte;
}UINT16_VAL;

static SPI_TypeDef *spi __attribute__((aligned (4))) = (SPI_TypeDef *) 0x0;

//#define UINT32_VAL uint32_t
//#define UINT16_VAL uint16_t
#define CMD_SERIAL_WRITE 0x02
#define CMD_FAST_READ 0x0e
#define CMD_FAST_READ_DUMMY 0x01

void spi_init()
{
  bool success = true;

  SYS_EnableAHBClock(AHB_MASK_DMAC0);
  DMAC_Init();

  // Use PERIPHERAL_ENABLE_ALL to enable all SPI pins, including SPI0_WPN_IO2 and SPI0_HOLDN_IO3
  PERIPHERAL_ENABLE_ALL(SPI, 0);
  INT_EnableIRQ(SPIx_IRQn(0), SPI_PRIORITY);

  spi = SPIx(0);

  DMAC_DisableSyncRequest(SPI_TX_DMA_REQ(spi));
  DMAC_DisableSyncRequest(SPI_RX_DMA_REQ(spi));

  uint32_t pclk_freq = SYS_GetPclkFreq();
  SPI_SclkDivTypeDef spi_sclk_div = pclk_freq > 240 ? SPI_CTRL_SCLK_DIV16 : pclk_freq > 120 ? SPI_CTRL_SCLK_DIV8 : SPI_CTRL_SCLK_DIV4;
  SPI_Init(spi, spi_sclk_div);

}

void SPIWriteDWord (uint16_t Address, uint32_t Val)
{
    UINT32_VAL dwData;
    UINT16_VAL wAddr;

    wAddr.Val  = Address;
    dwData.Val = Val;
    //Assert CS line
    //CSLOW();
    //Write Command
    //原ST代码
    // SPIWriteByte(CMD_SERIAL_WRITE);//0x02
    // //Write Address
    // SPIWriteByte(wAddr.byte.HB);//addr
    // SPIWriteByte(wAddr.byte.LB);//addr
    // //Write Bytes
    // SPIWriteByte(dwData.byte.LB);//write_data
    // SPIWriteByte(dwData.byte.HB);//write_data
    // SPIWriteByte(dwData.byte.UB);//write_data
    // SPIWriteByte(dwData.byte.MB);//write_data
/////////////////////////////////////////////////////////////////////////////////
//SPI_Send_Long(SPI_TypeDef *spi, uint8_t *txBuff, int txLen)
  DMAC_ChannelNumTypeDef tx_spi_dmac_channel = DMAC_CHANNEL6;

  SYS_EnableAHBClock(AHB_MASK_DMAC0);
  DMAC_Init();

  DMAC_DisableSyncRequest(SPI_TX_DMA_REQ(spi));
  DMAC_DisableSyncRequest(SPI_RX_DMA_REQ(spi));
  DMAC_EnableChannel(tx_spi_dmac_channel);
    uint8_t txBuff[10];
    int txLen=7;
    txBuff[0]=CMD_SERIAL_WRITE;//0x02
    txBuff[1]=wAddr.byte.HB;
    txBuff[2]=wAddr.byte.LB;
    txBuff[3]=dwData.byte.LB;
    txBuff[4]=dwData.byte.HB;
    txBuff[5]=dwData.byte.UB;
    txBuff[6]=dwData.byte.MB;
  uint32_t txData = 0;
  txData = txBuff[0] + (txBuff[1] << 8) + (txBuff[2] << 16) + (txBuff[3] << 24);

  SPI_SetPhaseCtrl(spi, SPI_PHASE_0, SPI_PHASE_ACTION_TX, SPI_PHASE_MODE_SINGLE, 4); //配置第一个PHASE为 TX
  SPI_SetPhaseData(spi, SPI_PHASE_0, txData); //配置要发送的数据
  // Command phase is always the first phase and tx 1 byte in single mode
  SPI_SetPhaseCtrl(spi, SPI_PHASE_1, SPI_PHASE_ACTION_TX, SPI_PHASE_MODE_SINGLE, txLen-4); //配置第二个PHASE为 DMA TX
  //配置要发送的数据(DMA方式)
  DMAC_Config(tx_spi_dmac_channel, (uint32_t)txBuff+4, (uint32_t)&spi->PHASE_DATA[SPI_PHASE_1],
              DMAC_ADDR_INCR_ON, DMAC_ADDR_INCR_OFF, DMAC_WIDTH_32_BIT, DMAC_WIDTH_32_BIT,
              DMAC_BURST_1, DMAC_BURST_1, 0, DMAC_MEM_TO_PERIPHERAL_PERIPHERAL_CTRL,
              0, SPI_TX_DMA_REQ(spi));

  SPI_Start(spi, SPI_CTRL_PHASE_CNT2, SPI_CTRL_DMA_ON, SPI_INTERRUPT_OFF); //启动SPI（有两个PHASE）
  SPI_WaitForDone(spi);

  DMAC_DisableChannel(tx_spi_dmac_channel);
    //De-Assert CS line
   // CSHIGH();
}

uint32_t SPIReadDWord (uint16_t Address)
{
    UINT32_VAL dwResult;
    UINT16_VAL wAddr;
		
    wAddr.Val  = Address;
    //Assert CS line
    //原ST代码
   // CSLOW();
    //Write Command
    //  SPIWriteByte(CMD_FAST_READ);//0x0B
    // //Write Address
    // SPIWriteByte(wAddr.byte.HB);//ADDR
    // SPIWriteByte(wAddr.byte.LB);//ADDR
    
    // //Dummy Byte
    // SPIWriteByte(CMD_FAST_READ_DUMMY);//0X01
    // //Read Bytes
    // dwResult.byte.LB = SPIReadByte();//Read_Data
    // dwResult.byte.HB = SPIReadByte();//Read_Data
    // dwResult.byte.UB = SPIReadByte();//Read_Data
    // dwResult.byte.MB = SPIReadByte();//Read_Data
    //De-Assert CS line
   // CSHIGH();//(void *)dwResult.Val.CRH
/////////////////////////////////////////////////////////////////////////////////////////////////////
//SPI_SendAndRecv_Short(SPI_TypeDef *spi, uint8_t *txBuff, int txLen, uint8_t *rxBuff, int rxLen)
  int rxLen=4,txLen=4;
  uint8_t txBuff[10],rxBuff[10];
  uint32_t txData = 0, rxData = 0;
    txBuff[0]=CMD_FAST_READ;//0x0b
    txBuff[1]=wAddr.byte.HB;
    txBuff[2]=wAddr.byte.LB;
    txBuff[3]=CMD_FAST_READ_DUMMY;//0x01
  if (txLen <= 4) txData = txBuff[0] + (txBuff[1] << 8) + (txBuff[2] << 16) + (txBuff[3] << 24);

  // Command phase is always the first phase and tx 1 byte in single mode
  SPI_SetPhaseCtrl(spi, SPI_PHASE_0, SPI_PHASE_ACTION_TX, SPI_PHASE_MODE_SINGLE, txLen); //配置第一个PHASE为 TX
  SPI_SetPhaseData(spi, SPI_PHASE_0, txData); //配置要发送的数据

  SPI_SetPhaseCtrl(spi, SPI_PHASE_1, SPI_PHASE_ACTION_RX, SPI_PHASE_MODE_SINGLE, rxLen); //配置第二个PHASE为 RX
  
  SPI_Start(spi, SPI_CTRL_PHASE_CNT2, SPI_CTRL_DMA_OFF, SPI_INTERRUPT_OFF); //启动SPI（有两个PHASE）
  SPI_WaitForDone(spi);

  rxData = spi->PHASE_DATA[SPI_PHASE_1]; //拿RX对应的数据
  rxBuff[0] = rxData & 0xFF;
  rxBuff[1] = (rxData >> 8) & 0xFF;
  rxBuff[2] = (rxData >> 16) & 0xFF;
  rxBuff[3] = (rxData >> 24) & 0xFF;

    dwResult.byte.LB = rxBuff[0] ;//Read_Data
    dwResult.byte.HB = rxBuff[1] ;//Read_Data
    dwResult.byte.UB = rxBuff[2] ;//Read_Data
    dwResult.byte.MB = rxBuff[3] ;//Read_Data
    return dwResult.Val;//display hex  (void *)&dwResult.Val   显示地址hex
}//display hex   (void **)dwResult.Val 显示寄存器hex

void testSPI()
{
  spi_init();
  SPIWriteDWord(0x11, 0x01);

  //SPIReadDWord(0x12);

}

#endif
